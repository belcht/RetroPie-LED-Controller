#!/bin/bash
# sync-to-repo.sh - Copy live files to repo and push

cd /home/pi/RetroPie-LED-Controller || exit 1

cp /home/pi/LEDControl/LEDControl.py .
cp /home/pi/LEDControl/update_config.py .
cp /home/pi/LEDControl/led-game-start.sh .
cp /home/pi/LEDControl/led-game-end.sh .
cp /home/pi/ledcontrol.toml .
sudo cp /etc/systemd/system/ledcontrol.service .
sudo cp /etc/systemd/system/leds-off.service .
sudo cp /usr/local/bin/leds-off-on-shutdown.sh .
cp ~/RetroPie-Setup/scriptmodules/supplementary/ledcontrol.sh .

git add .
git commit -m "Sync: updated from live Pi system $(date '+%Y-%m-%d %H:%M')"
git push origin main
