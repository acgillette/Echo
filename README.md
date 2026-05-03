# Echo, a solo journaling game 

## What is Echo 
Echo is a small proof of concept solo journaling game. It uses a structure called a grammar. An initial seed of different parts of speech (noun, quality, action, verb_past in this case) is used for prompts, which are presented to the person using it. You can then pick some words that resonate with the prompt, or type your own. When a session is ended, the words chosen are parsed by a light weight tagger and added to the grammar structure, so your prompts change over time as you keep using it. 

Right now this is a very bare bones proof of concept. It all lives in just the main.py file, which loads or makes a grammar json, handles the prompts and tagging and transitions from sessions back to home. It still needs a lot of manual work to parse and have the prompts make sense, as well as adding more prompts. Future work might look like making more complicated grammar structures from user input, showing basic sentiment analysis over time, or making a funky cute 3d case for it. 

## How to setup 
Echo is built using [Micropython-LVGL](https://github.com/de-dh/ESP32-Cheap-Yellow-Display-Micropython-LVGL) on a [Cheap Yellow Display](https://deepwiki.com/witnessmenow/ESP32-Cheap-Yellow-Display/2.1-hardware-overview). As I am not a hardware person I tried to keep things as simple as possible. 

1. The only packages you need locally are ```esptool``` and ```mpremote```. Install these in your local python environment. 

2. Then clone the Micropython-LVGL repo: ```git clone https://github.com/de-dh/ESP32-Cheap-Yellow-Display-Micropython-LVGL.git```

3. Change into the firmware directory: ```cd ESP32-Cheap-Yellow-Display-Micropython-LVGL/lvgl9_firmware```

4. With your cheap yellow display connected to your computer, flash in the Micropython-LVGL .bin file: 
```python3 -m esptool --chip esp32 --port /dev/cu.usbserial-2110 \
  -b 460800 \
  --before default_reset \
  --after hard_reset \
  write_flash \
  --flash-mode dio \
  --flash-size 4MB \
  --flash-freq 40m \
  --erase-all \
  0x0 lvgl9_3_micropython_cyd.bin```
  
  5. Then, in the same directory as ```main.py``` and the cheap yellow display connected, run the command to run main onto the board: ```python3 -m mpremote connect /dev/cu.usbserial-2110 run main.py```
  
  
## Modifying the code 

1. The SEED constant holds the initial words that can be picked by the prompt. New parts of speech can be easily added by adding to the object structure. 

2. If you look on line 101 on the prompts you will see that each prompt has a structure where a part of speech is surrounded by # signs. When making your own prompts or adding parts of speech, simply use this format and ensure the part of speech inside the # signs match with a key in the seed object. 

3. There are some random injected prompts that can appear randomly (1 in 6 chance). The odds can be changed by modifying the randint on line 121, and the stranger prompts live in the STRANGERS variable on line 111. 


