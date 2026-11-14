from __future__ import annotations

from entertainment_pipeline.config import ProcessorSettings, ProducerSettings


KAFKA_SECURITY_ENV = {
    "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
    "KAFKA_SASL_MECHANISM": "SCRAM-SHA-512",
    "KAFKA_SASL_USERNAME": "pipeline-user",
    "KAFKA_SASL_PASSWORD": "injected-at-runtime",
    "KAFKA_SSL_CA_LOCATION": "/etc/ssl/certs/ca.pem",
}


def test_local_kafka_config_does_not_require_security(monkeypatch) -> None:
    for name in KAFKA_SECURITY_ENV:
        monkeypatch.delenv(name, raising=False)

    config = ProducerSettings.from_env().kafka_config()

    assert "security.protocol" not in config
    assert config["bootstrap.servers"] == "localhost:29092"


def test_tls_sasl_settings_are_shared_by_producer_and_consumer(monkeypatch) -> None:
    for name, value in KAFKA_SECURITY_ENV.items():
        monkeypatch.setenv(name, value)

    producer_config = ProducerSettings.from_env().kafka_config()
    consumer_config = ProcessorSettings.from_env().kafka_config()

    for key, expected in {
        "security.protocol": "SASL_SSL",
        "sasl.mechanism": "SCRAM-SHA-512",
        "sasl.username": "pipeline-user",
        "sasl.password": "injected-at-runtime",
        "ssl.ca.location": "/etc/ssl/certs/ca.pem",
    }.items():
        assert producer_config[key] == expected
        assert consumer_config[key] == expected
