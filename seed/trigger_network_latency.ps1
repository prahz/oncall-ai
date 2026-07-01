$jsonFile = Join-Path $PSScriptRoot "network_latency_req.json"
lemma record create alerts --file $jsonFile
