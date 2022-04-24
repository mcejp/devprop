from devprop.manifest import parse_manifest_yaml, validate_manifest


def test_manifest_validation():
    manifest_yaml = """
    device_name: Silly-Name
    properties:
      - name: BadMinMax
        type: int8
        range: [-200, 200]
      - name: BadMinMax2
        type: int8
        scale: 0.1
        range: [-20, 20]
      - name: BadRange
        type: int8
        range: [100, 0]
      - name: BadScale
        type: uint8
        scale: 0.000000001
    """

    manifest = parse_manifest_yaml(manifest_yaml)
    errors = validate_manifest(manifest)
    messages = [str(e) for e in errors]

    assert any("BadMinMax: specified minimum" in m for m in messages)
    assert any("BadMinMax: specified maximum" in m for m in messages)
    assert any("BadMinMax2: specified minimum" in m for m in messages)
    assert any("BadMinMax2: specified maximum" in m for m in messages)
    assert any("BadRange: maximum must be larger than minimum" in m for m in messages)
    assert any("BadScale: scale must not be zero" in m for m in messages)
