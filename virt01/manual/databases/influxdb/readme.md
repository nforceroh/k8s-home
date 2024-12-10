# Create org "my-org"

```
influx org create -n nf
```

# Create a bucket

```
influx bucket create -o nf -n upsdata/autogen --retention 3h20m --shard-group-duration 1h
```

# Create "collectd" user with write access to bucket "collectd/autogen"

```
BUCKET=$(influx bucket list --hide-headers -n upsdata/autogen | awk '{print $1}')
influx auth create --org nf --description 'upsdata' --read-bucket $BUCKET --write-bucket $BUCKET

```
fliIm1NrpF6ZQ5s1_OYNyStUN48ubNOx7D-foWcDt6o0mskxYg_im3uVqRi9ZN6_Ayx0O_yn4gVPU2VseaR6ig==

# upsdata downsampling buckets

```
influx bucket create -o nf -n upsdata/day --retention 1d --shard-group-duration 1h
influx bucket create -o nf -n upsdata/week --retention 7d --shard-group-duration 1d
influx bucket create -o nf -n upsdata/month --retention 31d --shard-group-duration 1d
influx bucket create -o nf -n upsdata/year --retention 366d --shard-group-duration 7d
```

# bucket autoselecting for grafana

```
influx bucket create -o nf -n upsdata/forever --retention 0

influx write -o nf --bucket upsdata/forever '
rp_config,idx=1 rp="autogen",start=0i,end=12000000i,interval="10s" -9223372036854775806
rp_config,idx=2 rp="day",start=12000000i,end=86401000i,interval="60s" -9223372036854775806
rp_config,idx=3 rp="week",start=86401000i,end=604801000i,interval="300s" -9223372036854775806
rp_config,idx=4 rp="month",start=604801000i,end=2678401000i,interval="1800s" -9223372036854775806
rp_config,idx=5 rp="year",start=2678401000i,end=31622401000i,interval="21600s" -9223372036854775806
'
```

# A separate grafana user is required with read access to the required buckets

# Create "grafana" user with read access for the "upsdata/*" buckets

```
BUCKET_AUTOGEN=$(influx bucket list --hide-headers -n upsdata/autogen | awk '{print $1}')
BUCKET_DAY=$(influx bucket list --hide-headers -n upsdata/day | awk '{print $1}')
BUCKET_WEEK=$(influx bucket list --hide-headers -n upsdata/week | awk '{print $1}')
BUCKET_MONTH=$(influx bucket list --hide-headers -n upsdata/month | awk '{print $1}')
BUCKET_YEAR=$(influx bucket list --hide-headers -n upsdata/year | awk '{print $1}')
BUCKET_FOREVER=$(influx bucket list --hide-headers -n upsdata/forever | awk '{print $1}')
influx auth create --org nf --description 'grafana' --read-bucket $BUCKET_AUTOGEN --read-bucket $BUCKET_DAY --read-bucket $BUCKET_WEEK --read-bucket $BUCKET_MONTH --read-bucket $BUCKET_YEAR --read-bucket $BUCKET_FOREVER
```

2MMV2Fc4HfueJHozVHsqUfPm-d4kTWfvo-SgJKm00gBbQVg_t3d2kJ4K7Y3eItfueun_Lqb9B5HWVYnSD_p97w==
# flux tasks

# Copy autogen to day

```
cat <<EOT > upsdata_downsample_day
option task = {name: "upsdata_downsample_day", every: 1m}

from(bucket: "upsdata/autogen")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 1m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/day")
EOT
influx task create -org nf -f upsdata_downsample_day
```

# Copy day to week

```
cat <<EOT > upsdata_downsample_week
option task = {name: "upsdata_downsample_week", every: 5m}

from(bucket: "upsdata/autogen")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 5m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/week")
EOT
influx task create -org nf -f upsdata_downsample_week
```

# Copy day to month

```
cat <<EOT > upsdata_downsample_month
option task = {name: "upsdata_downsample_month", every: 30m}

from(bucket: "upsdata/day")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 30m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/month")
EOT
influx task create -org nf -f upsdata_downsample_month
```

# copy day to year

```
cat <<EOT > upsdata_downsample_year
option task = {name: "upsdata_downsample_year", every: 6h}

from(bucket: "upsdata/day")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 6h, fn: mean)
    |> to(org: "nf", bucket: "upsdata/year")
EOT
influx task create -org nf -f upsdata_downsample_year
```

# copy bucket to another

```
export INFLUX_TOKEN=qk2fjU_1wxswBW-WvUgQFTrqKC5adgKg1aRt1Xjbsuog44wIJGA_vY6e1ObAdR800XeJqJ_q0YMy-f7XA7nrLQ==
export INFLUX_ORG=nf
export INFLUX_HOST=http://localhost:8086

influx delete --bucket upsdata/autogen  --start 2010-03-01T00:00:00Z --stop 2030-03-01T00:00:00Z
influx query 'from(bucket:"upsdata") |> range(start: -1y) |> to(bucket: "upsdata/autogen", org: "nf")'  > /dev/null
```

# number of rows

```
from(bucket: "upsdata")
  |> range(start: -2y)
  |> group()  
  |> count()


from(bucket: "upsdata/autogen")
  |> range(start: -2y)
  |> group()  
  |> count()

```

influx query 'from(bucket:"upsdata/autogen") |> range(start: -30d) |> filter(fn: (r) => r["_field"] != "ups_status" ) |> aggregateWindow(every: 1m, fn: mean) |> to(org: "nf", bucket: "upsdata/day")'  > /dev/null
influx query 'from(bucket:"upsdata/autogen") |> range(start: -1y) |> filter(fn: (r) => r["_field"] != "ups_status" ) |> aggregateWindow(every: 5m, fn: mean) |> to(org: "nf", bucket: "upsdata/week")'  > /dev/null
influx query 'from(bucket:"upsdata/autogen") |> range(start: -1y) |> filter(fn: (r) => r["_field"] != "ups_status" ) |> aggregateWindow(every: 30m, fn: mean) |> to(org: "nf", bucket: "upsdata/month")'  > /dev/null
influx query 'from(bucket:"upsdata/autogen") |> range(start: -1y) |> filter(fn: (r) => r["_field"] != "ups_status" ) |> aggregateWindow(every: 6h, fn: mean) |> to(org: "nf", bucket: "upsdata/year")'  > /dev/null

from(bucket: "upsdata/autogen")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 1m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/day")

```
# Copy day to week
```

option task = {name: "upsdata_downsample_week", every: 5m}

from(bucket: "upsdata/autogen")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 5m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/week")

```

# Copy day to month
```

option task = {name: "upsdata_downsample_month", every: 30m}

from(bucket: "upsdata/day")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 30m, fn: mean)
    |> to(org: "nf", bucket: "upsdata/month")

```

# copy day to year
```

option task = {name: "upsdata_downsample_year", every: 6h}

from(bucket: "upsdata/day")
    |> range(start: -task.every)
    |> filter(fn: (r) => r["_field"] != "ups_status" )
    |> aggregateWindow(every: 6h, fn: mean)
    |> to(org: "nf", bucket: "upsdata/year")

```

# http://wiki.webperfect.ch/index.php?title=Grafana:_Dynamic_Retentions_%28InfluxDB%29
# grafana variable template
```

    //Bucketfilter to filter only buckets beginning with name upsdata..
    bucketfilter = /upsdata.*/

    buckets()
    |> filter(fn: (r) => r.name =~ bucketfilter)
    //convert retentionperiod from nanosecond to days
    |> map(fn: (r) => ({r with retentionPeriodinDays: r.retentionPeriod / 86400000000000})   )
    //replace retentionpolicy infinity with a high number in NS
    |> map(fn: (r) => ({r with retentionPeriod: if r.retentionPeriod == 0 then 999999999999999999
        else r.retentionPeriod})
    )
    //calculate the duration from "to" and "from" timespan and convert it to nanosecond
    |> map(fn: (r) => ({r with 
        DashboardDurationinNS: (${__to} - ${__from}) * 1000000})
    )
    |> filter(fn: (r) => 
        r.DashboardDurationinNS <= r.retentionPeriod and
        r.retentionPeriod >= uint(v: now()) - uint(v: ${__from} * 1000000)
    )
    |> sort(columns: ["retentionPeriod"], desc: false)
    |> limit(n: 1)
    |> keep(columns: ["name"]) //remove all fields except for "name"

```

option task = {name: "mysensors_downsample", every: 5m}

from(bucket: "mysensors")
    |> range(start: -task.every)
    |> aggregateWindow(every: 5m, fn: mean)
    |> to(org: "nf", bucket: "mysensors/5m_avg")
```

influxdb-856c9c7546-sfj7n:/# influx auth list
ID                      Description     Token                                                                                           User Name       User ID                 Permissions
0b9741d8213d2000        admin's Token   AAfhqI_H8HVllnUILPYm0cYufi9trJPYKQ9vWBxwDEvN8nbUGP8bekFlYqkIRt5xulGFxuGVpyZYN2cWWK8jZA==        admin           0b9741d7d07d2000        [read:/authorizations write:/authorizations read:/buckets write:/buckets read:/dashboards write:/dashboards read:/orgs write:/orgs read:/sources write:/source
s read:/tasks write:/tasks read:/telegrafs write:/telegrafs read:/users write:/users read:/variables write:/variables read:/scrapers write:/scrapers read:/secrets write:/secrets read:/labels write:/labels read:/views write:/views read:/documents write:/documents read:/notificationRules write:/notificationRules read:/notificationEndp
oints write:/notificationEndpoints read:/checks write:/checks read:/dbrp write:/dbrp read:/notebooks write:/notebooks read:/annotations write:/annotations read:/remotes write:/remotes read:/replications write:/replications]
0b9742ccb1fe6000        grafana         2MMV2Fc4HfueJHozVHsqUfPm-d4kTWfvo-SgJKm00gBbQVg_t3d2kJ4K7Y3eItfueun_Lqb9B5HWVYnSD_p97w==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2 read:orgs/061784c7d7d1bd0e/buckets/a60c3d4d9e6f8d7b read:orgs/061784c7d7d1bd0e/buckets/dd65573e0a33e7b1 r
ead:orgs/061784c7d7d1bd0e/buckets/5881066b77b8178d read:orgs/061784c7d7d1bd0e/buckets/0875b0e41318c646 read:orgs/061784c7d7d1bd0e/buckets/949eb961ed40f04a]
0b974481db298000        upsdata         fliIm1NrpF6ZQ5s1_OYNyStUN48ubNOx7D-foWcDt6o0mskxYg_im3uVqRi9ZN6_Ayx0O_yn4gVPU2VseaR6ig==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2 write:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2]
0b99ebfaef1ef000        mysensors       E3roDiq5uRAUubsxMMaJkHrjRvpIn2sI7uxzyRpav7hzDTiBKq0mpEZgIP5AqNsHoMr0MnJzxzQwVw_mdYVlpw==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/cf68f39a70d2285d write:orgs/061784c7d7d1bd0e/buckets/cf68f39a70d2285d]
0bbfa4fa48298000        upsdata sender  pBs3chUS-Of-uSijVLEbM_N7vPNgEfrzum1WMQ3qbuDhZM7z6AiIC6N2S7tWNetXV9OJf8DIcOqnq2qUfrI9hA==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2 write:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2]
0c22e471994fc000        upsdata         ZvsNsiRBZnBK07Uobq8ClXB--k59M27tjNfWX-e_qnZ-CgFtnjc9yoXv-fW3Tnw58TcD5-LpJk98oWZoCsvBmw==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2 write:orgs/061784c7d7d1bd0e/buckets/0c336c76bb41bde2]
0c41569b30022000        HTCC            Gg2P5GvyR1asQANAW2Fd_lmToGLoPd4xAq3ohflEa6Ux6WY_4V4cF9z2oHNRpbCg6maGYqCUeHygqW0qwgm6Kw==        admin           0b9741d7d07d2000        [read:orgs/061784c7d7d1bd0e/buckets/47a4de6f7354f61f write:orgs/061784c7d7d1bd0e/buckets/47a4de6f7354f61f]
influxdb-856c9c7546-sfj7n:/#