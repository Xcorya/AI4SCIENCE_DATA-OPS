"""Evidence policy reference, not a pretrained image/video recognizer.

Increment ENGINE_VERSION whenever acceptance, calibration or reward semantics
change. The version is part of the certificate fingerprint; a release may not
reuse a prior engine's certification merely because its config is unchanged.
Production deployments can additionally bind the full immutable source revision.
"""

ENGINE_VERSION = "0.1.1"
__version__ = ENGINE_VERSION
