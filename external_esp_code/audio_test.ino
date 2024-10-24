#include "SoundData.h";
#include "XT_DAC_Audio.h";
#include "Arduino.h";

XT_Wav_Class doorCloser(doorsClosing);

XT_DAC_Audio_Class DacAudio(25, 0);

void setup(){
    Serial.begin(115200);
}

void loop(){
    DacAudio.FillBuffer();
    if(doorCloser.Playing == false){
        Serial.println("Playing new doorCloser Effect");
        DacAudio.Play(&doorCloser);
    }
}