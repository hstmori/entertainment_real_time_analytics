param(
    [Parameter(Mandatory = $true)]
    [string]$BootstrapServers,

    [Parameter(Mandatory = $true)]
    [string]$CommandConfig,

    [string]$KafkaTopicsCommand = "kafka-topics.bat",
    [int]$Partitions = 3,
    [int]$ReplicationFactor = 3
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $CommandConfig)) {
    throw "Kafka command config not found: $CommandConfig"
}
if ($Partitions -lt 1 -or $ReplicationFactor -lt 1) {
    throw "Partitions and ReplicationFactor must be positive."
}

$topics = @(
    "entertainment.user-activity.v1",
    "entertainment.booking.v1",
    "entertainment.subscription.v1",
    "entertainment.event-attendance.v1",
    "entertainment.dead-letter.v1"
)

foreach ($topic in $topics) {
    & $KafkaTopicsCommand `
        --bootstrap-server $BootstrapServers `
        --command-config $CommandConfig `
        --create `
        --if-not-exists `
        --topic $topic `
        --partitions $Partitions `
        --replication-factor $ReplicationFactor
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create or verify topic: $topic"
    }
}

& $KafkaTopicsCommand --bootstrap-server $BootstrapServers --command-config $CommandConfig --list
if ($LASTEXITCODE -ne 0) { throw "Failed to list Kafka topics." }
