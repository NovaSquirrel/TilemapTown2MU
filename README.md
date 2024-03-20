# TilemapTown2MU

This is a silly proof-of-concept protocol gateway that allows you to connect to [Tilemap Town](https://novasquirrel.com/town/) using a MUD/MUCK/MUSH/etc. client like BeipMU. If you want to run this, you will want to make sure the connection URI in `gateway.py` is what you want.

There are some commands available for interacting with the map:
* `show` - Show the map around your avatar
* `bigshow` - Show a larger portion of the map
* `.` - Show a small portion of the map around your avatar
* `. s` - Move one tile downwards, and show the map around your new position. You can use `w`, `a`, `s`, and `d` to specify a direction to move, and you can write out a series of steps to take, like `. aaaa` or `. wwaassdd`
* `?turf` - Get the name of the type of floor you're standing on.
* `?turf x y` - Get the name of a type of floor near you. `x y` is an offset relative to your position. You can also use `w`, `a`, `s`, or `d` to specify one tile away from you in a cardinal direction.
* `?obj x y` - Get the name of objects near you
* `"text` - Say text as your avatar
* `:text` - Do an action as your avatar
* `/command` - Do one of the regular Tilemap Town commands, just as in the regular client

The following commands/aliases will also pass through without requiring a `/`:
* tell, roll, away, status, nick, userdesc, userpic, login, register, changepass, who, entitywho, gwho, look, last, goback, tpa, tpahere, tpaccept, tpdeny, tpcancel, sethome, home, carry, followme, hopon, hopoff, dropoff, rideend, carrywho, ridewho, giveitem, publicmaps, publicmaps, mapid, map, time, listeners, entity, e, msg, stat, findrp, findiic, tpi, whereare, wa, ewho, whoami, p, topic, cleartopic
