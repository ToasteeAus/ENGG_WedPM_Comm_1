bladeRunnerCommands = {
    "STOP": "00",
    "FORWARD-SLOW": "01",
    "FORWARD-FAST": "02",
    "REVERSE-SLOW": "03",
    "REVERSE-FAST": "04",
    "DOORS-OPEN": "05",
    "DOORS-CLOSE": "06",
    "SET-SLOW-SPEED": "07",
    "SET-FAST-SPEED": "08",
    "DISCONNECT": "FF"
}

bladeRunnerCommandsKey_list = list(bladeRunnerCommands.keys())
bladeRunnerCommandsVal_list = list(bladeRunnerCommands.values())

brAvail = ["BR28", "BR95"] # Available BladeRunners to control
opAvail = ["MCP", "MAN"]