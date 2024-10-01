# Intro

This guide should help get your own local VSCode Workspace setup with the required extensions for work within this ENGG2000/3000 Unit! (If you have any issues, please contact Toast or refer to online docs)

## Setup

1. Download [git](https://git-scm.com/downloads), and [VSCode](https://code.visualstudio.com/download) if you haven't already installed them on your machine.
2. Download Python at Version [3.10.0](https://www.python.org/downloads/release/python-3100/)
(To confirm your install, head to your terminal and insert either "python --version" or "python3 --version")
3. Clone this repo to your local machine
4. Open VSCode and select File > "Open Workspace from Folder"
5. When prompted, accept and download recommended extensions for this workspace
6. To finish installing PlatformIO, on the left hand menu select the alien icon for PlatformIO
7. Once done, reload your VSCode window
8. For some devices, they may natively support the chipset used to communicate between an ESP32 and your device, in case the ESP32 is not recognised, download the following driver with the correct version for your system, [install](https://www.silabs.com/developers/usb-to-uart-bridge-vcp-drivers?tab=downloads)
9. Inside VSCode, using the following command (MAC: cmd+shift+P, WIN:ctrl+shift+P) to open a prompt, enter and select "Python: Select Interpreter" and select 3.12.4 as you've installed

## Using Python

## Using PlatformIO
Ridiculously helpful [guide](https://randomnerdtutorials.com/vs-code-platformio-ide-esp32-esp8266-arduino/)

# Debugging the BladeRunner

When in operation the BladeRunner will expose 4 LEDS to display its current status, this will flash or become a solid colour representative of certain states.
Key states:
WiFi not connected - Flashing Amber
CCP not connected - Flashing Dark Blue
CCP connected, no commands sent - Solid Dark Blue
Stopped - Solid Red
Unknown state - Solid White

Other states represented:
Door Opening/Open - Flashing Amber/Solid Green
Door Closing/Closed - Flashing Amber/Solid Red
Forward, Slow - Solid Light Green/Aquarmarine
Forward, Fast - Solid Green
Reverse, Slow - Solid Light Blue
Reverse, Fast - Solid Dark Blue

(Slow = Lighter)

# Known limitations
Will fallover if MCP dies during operation -> this needs to be urgently resolved
Doesn't check for health of ESP even if MCP isn't actively sending requests -> Unlikely in prod environment but can occur frequently in testing (However, ESP can connect freely)
Cannot comprehend the LED IR Blink patterns -> near impossible and hoping the MCP teams are scrapping it
If the ESP detects it is at a station we will send back status with no station id -> Could cause issues with MCP given how theyre implemented, will only know tmrw