def test_configmap():
    configmap = ConfigMap("my-configmap", data={"key": "value"})
    assert configmap.name == "my-configmap"
    assert configmap.data == {"key": "value"}
    assert configmap.kind == "ConfigMap"
    assert configmap.apiVersion == "v1"
    assert configmap.metadata == {
        "name": "my-configmap",
        "namespace": "default",
    }
    assert configmap.to_dict() == {
        "apiVersion": "v1",
        "kind": "ConfigMap",
        "metadata": {"name": "my-configmap", "namespace": "default"},
        "data": {"key": "value"},
    }
