#!/bin/bash
# https://www.dell.com/support/kbdoc/en-dm/000136288/idrac-how-to-set-the-idrac-thermal-base-algorithm-via-cli

IDRAC_USER=fans
IDRAC_PW=fans
MAXTEMP=40
FANSPEED=5

function get_temp {
  local TEMP=$(ipmitool -I lanplus -H $IDRAC_HOST -U $IDRAC_USER -P $IDRAC_PW sdr type temperature | egrep "01h|^Temp"|head -1 | grep -o -e '[0-9][0-9] degrees' | grep -o -e '[0-9][0-9]')
  echo $TEMP
}

function set_dynamic {
  HEX=$(printf '0x%02x' $1)
  ipmitool -I lanplus -H $IDRAC_HOST -U $IDRAC_USER -P $IDRAC_PW raw 0x30 0x30 0x01 $HEX > /dev/null
}

function set_speed {
  HEX=$(printf '0x%02x' $1)
  ipmitool -I lanplus -H $IDRAC_HOST -U $IDRAC_USER -P $IDRAC_PW raw 0x30 0x30 0x02 0xff $HEX > /dev/null
}



for IDRAC_HOST in 192.168.101.200 192.168.101.199; do
  echo "Setting fan speed for $IDRAC_HOST"
  TEMP=$(get_temp)
  if [[ -n "$TEMP" && -n "$MAXTEMP" && "$TEMP" =~ ^[0-9]+$ && "$MAXTEMP" =~ ^[0-9]+$ && $TEMP -gt $MAXTEMP ]]; then
    echo "Exhaust Temperature is $TEMP C - Temperature is too high; using dynamic fan control"
    set_dynamic 1
  else
    echo "Exhaust Temperature is $TEMP C - Temperature is normal; using manual fan control of $FANSPEED %"
    set_dynamic 0
    set_speed $FANSPEED
  fi

done