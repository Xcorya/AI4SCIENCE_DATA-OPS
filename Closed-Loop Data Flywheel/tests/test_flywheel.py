import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError
from unittest.mock import patch

from helix.demo import seed
from helix.store import Store, split_for
from helix.pipeline import (run_pipeline, export_rows, record_feedback,
                            feedback_priorities, synthesize_artifact, confidence_points)
from helix.verifiers import numeric_reward, reference, grpo_reward
from helix.ingest import import_manifest, discover, validate_url
from helix.extractors import extract
from helix.server import make_server


class FlywheelTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(self.temp.name)
        seed(self.store)

    def tearDown(self):
        self.temp.cleanup()

    def test_seed_is_idempotent_and_original_objects_exist(self):
        self.assertEqual(seed(self.store)["created"], 0)
        self.assertEqual(len(self.store.all("assets")), 14)
        for a in self.store.all("assets"):
            self.assertTrue((Path(self.temp.name)/"objects"/a["object_sha256"]).is_file())

    def test_pipeline_idempotence(self):
        first = run_pipeline(self.store, 200)
        self.assertEqual(first["created"], 56)
        second = run_pipeline(self.store, 200)
        self.assertEqual(second["created"], 0)
        self.assertEqual(len(self.store.all("tasks")), 56)

    def test_default_export_excludes_all_demo_and_holdout(self):
        run_pipeline(self.store, 200)
        self.assertEqual(export_rows(self.store), [])
        for fmt in ("rl", "sft", "dpo"):
            rows = export_rows(self.store, fmt, include_demo=True)
            self.assertTrue(rows)
            self.assertTrue(all(r["metadata"]["split"] == "train" for r in rows))
            self.assertTrue(all(r["metadata"]["license"] != "unknown" for r in rows))
        with self.assertRaises(ValueError):
            export_rows(self.store, split="holdout")

    def test_truth_is_not_inserted_in_rl_prompt(self):
        run_pipeline(self.store, 200)
        for row in export_rows(self.store, include_demo=True):
            self.assertEqual(len(row["prompt"]), 1)
            self.assertNotIn("ground_truth", row["prompt"][0]["content"])
            self.assertEqual(row["prompt"][0]["role"], "user")
            self.assertIn("ground_truth", row)

    def test_family_split_is_shared_and_cannot_be_promoted(self):
        asset = next(a for a in self.store.all("assets") if a["split"] == "train")
        sibling = dict(asset, text="a different source representation", source_id="child", benchmark=False)
        child, added = self.store.add_asset(sibling)
        self.assertTrue(added)
        self.assertEqual(asset["split"], child["split"])
        with self.assertRaises(ValueError):
            self.store.add_asset(dict(sibling, text="benchmark addition", benchmark=True))
        with self.assertRaises(ValueError):
            self.store.add_asset(dict(asset, benchmark=True))

    def test_holdout_feedback_never_changes_sampling(self):
        run_pipeline(self.store, 200)
        task = next(t for t in self.store.all("tasks") if t["split"] == "holdout")
        before = feedback_priorities(self.store)
        record_feedback(self.store, task["id"], '{"answer":0,"unit":"wrong"}', "test")
        self.assertEqual(before, feedback_priorities(self.store))

    def test_failed_evaluation_increases_its_domain_priority(self):
        run_pipeline(self.store, 200)
        task = next(t for t in self.store.all("tasks") if t["split"] == "train")
        a = self.store.get("assets", task["asset_id"])
        d = a["classification"]["primary"]
        before = {p["discipline"]:p["weight"] for p in feedback_priorities(self.store)}
        record_feedback(self.store, task["id"], '{"answer":0,"unit":"wrong"}', "test")
        after = {p["discipline"]:p["weight"] for p in feedback_priorities(self.store)}
        self.assertGreater(after[d], before[d])

    def test_unknown_license_is_quarantined(self):
        run_pipeline(self.store, 200)
        tasks = [t for t in self.store.all("tasks") if t["license"] == "unknown"]
        self.assertEqual(len(tasks), 4)
        self.assertTrue(all(t["status"] != "accepted" for t in tasks))
        self.assertTrue(all(not t["gates"][0]["passed"] for t in tasks))

    def test_model_is_never_called_for_holdout_or_unknown_license(self):
        with patch("helix.providers.available", return_value=True), \
             patch("helix.providers.complete", return_value='{"answer":0,"unit":"Pa"}') as mock:
            run_pipeline(self.store, 200, "model")
        denied = [a["title"] for a in self.store.all("assets")
                  if a["split"] == "holdout" or a["license"] == "unknown"]
        self.assertTrue(mock.call_count)
        self.assertFalse(any(title in call.args[0] for title in denied for call in mock.call_args_list))

    def test_generated_open_ended_artifacts_remain_review(self):
        asset = next(a for a in self.store.all("assets") if a["split"] == "train" and a["license"] != "unknown")
        for kind in ("qa", "pipeline", "paper"):
            result = synthesize_artifact(self.store, asset["id"], kind)
            self.assertEqual(result["status"], "review")
            self.assertIn("artifact", result)
        holdout = next(a for a in self.store.all("assets") if a["split"] == "holdout")
        with self.assertRaises(ValueError):
            synthesize_artifact(self.store, holdout["id"], "paper")

    def test_unbound_facts_cannot_pass_evidence_gate(self):
        base = next(a for a in self.store.all("assets") if a["split"] == "train")
        asset, _ = self.store.add_asset(dict(base, text="claims unsupported by the recorded facts"))
        run_pipeline(self.store, 200)
        tasks = [t for t in self.store.all("tasks") if t["asset_id"] == asset["id"]]
        self.assertTrue(tasks)
        self.assertTrue(all(not t["gates"][1]["passed"] for t in tasks))

    def test_import_csv_stores_real_bytes_and_parsed_facts(self):
        Path(self.temp.name, "obs.csv").write_text("t,value\n0,3\n1,7\n")
        item = {"title":"CSV", "source_id":"csv-test", "source_url":"demo://csv-test",
                "license":"CC0-1.0", "modality":"table", "text":"original data",
                "local_file":"obs.csv", "extract":{"format":"csv","column":"value","unit":"Pa"},
                "is_demo":True}
        result = import_manifest(self.store, [item], self.temp.name)
        self.assertEqual(result["errors"], [])
        asset = next(a for a in self.store.all("assets") if a["source_id"] == "csv-test")
        self.assertEqual(asset["facts"]["values"], [3.,7.])
        self.assertEqual(asset["extraction"]["source_sha256"], asset["object_sha256"])

    def test_local_path_escape_is_rejected(self):
        item = dict(self.store.all("assets")[0], local_file="../outside")
        result = import_manifest(self.store, [item], self.temp.name)
        self.assertEqual(len(result["errors"]), 1)


class VerifierTest(unittest.TestCase):
    def test_independent_reference_values(self):
        self.assertEqual(reference("mean", [1,2,3]), 2)
        self.assertEqual(reference("delta", [5,2,9]), 4)
        self.assertEqual(reference("ratio", [2,8]), 4)
        self.assertEqual(reference("range", [-2,3]), 5)
        with self.assertRaises(ValueError):
            reference("ratio", [0,1])
        with self.assertRaises(ValueError):
            reference("mean", [1,float("nan")])

    def test_strict_reward_rejects_reward_hacking(self):
        truth = {"answer":2., "unit":"Pa"}
        self.assertEqual(numeric_reward('{"answer":2,"unit":"Pa"}',truth),1)
        for bad in ['{"answer":true,"unit":"Pa"}','{"answer":NaN,"unit":"Pa"}',
                    '{"answer":"2","unit":"Pa"}','{"answer":2,"unit":"kPa"}',
                    '{"answer":2}',"I think 2 Pa", '{"answer":Infinity,"unit":"Pa"}', "null", "[]"]:
            self.assertEqual(numeric_reward(bad,truth),0,bad)

    def test_grpo_conversational_reward(self):
        self.assertEqual(grpo_reward([[{"role":"assistant","content":'{"answer":2,"unit":"Pa"}'}]],
                                     [{"answer":2,"unit":"Pa"}]), [1.0])

    def test_confidence_boundaries(self):
        self.assertEqual([confidence_points(p) for p in [.8,.9,.92,.95,.97,.99]], [0,1,1,2,2,3])

    def test_raw_extractors(self):
        self.assertEqual(extract(b">a\nACG\n>b\nACGT\n", {"format":"fasta"})["values"], [3,4])
        xyz=b"3\nsample\nC 0 0 0\nH 1 0 0\nH 0 2 0\n"
        self.assertEqual(extract(xyz,{"format":"xyz"})["values"], [1,2])
        stl=b"solid s\nvertex 0 0 0\nvertex 1 0 0\nvertex 0 1 0\nvertex 0 0 0\nvertex 2 0 0\nvertex 0 2 0\nendsolid"
        self.assertEqual(extract(stl,{"format":"stl","unit":"mm"})["values"], [.5,2])
        with self.assertRaises(ValueError):
            extract(b"t,x\n0,NaN\n1,3\n",{"format":"csv","column":"x","unit":"Pa"})

    def test_network_allowlist(self):
        for url in ["http://arxiv.org/a", "https://localhost/x", "file:///etc/passwd",
                    "https://arxiv.org@127.0.0.1/x", "https://arxiv.org:444/x"]:
            with self.assertRaises(ValueError):
                validate_url(url)


class HTTPTest(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(self.temp.name)
        self.server=make_server(self.store, port=0)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
        self.base="http://127.0.0.1:"+str(self.server.server_address[1])

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join()
        self.temp.cleanup()

    def test_api_seed_state_csrf_and_path_boundaries(self):
        with urlopen(self.base+"/api/session") as r:
            token=json.load(r)["token"]
        req=Request(self.base+"/api/demo",data=b"{}",headers={"X-Helix-Token":token})
        with urlopen(req) as r:
            self.assertEqual(json.load(r)["created"],14)
        with urlopen(self.base+"/api/state") as r:
            self.assertEqual(json.load(r)["stats"]["assets"],14)
        with self.assertRaises(HTTPError) as error:
            urlopen(Request(self.base+"/api/demo",data=b"{}"))
        self.assertEqual(error.exception.code,403)
        with self.assertRaises(HTTPError) as error:
            urlopen(self.base+"/../helix/store.py")
        self.assertEqual(error.exception.code,404)
        with urlopen(self.base+"/") as r:
            self.assertIn(b"HELIX",r.read())


if __name__ == "__main__":
    unittest.main()
