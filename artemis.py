#!/usr/bin/env python

# I wrote significant parts of this while exhausted.
# Apologies in advance to myself or whoever else reads it.

import asyncio
import datetime
import itertools
import os
from skyfield import almanac, api, eclipselib

# Options include:
# - de421.bsp: ~17 MiB, 1900-2050
# - de422.bsp: ~623 MiB, -3000-3000
# - de440s.bsp: ~32 MiB, 1849-2150
# - de440.bsp: ~114 MiB, 1550-2650
# - de441.bsp: ~3.1 GiB, -13200-17191
EPHEMERIS_DATA = 'de441.bsp'

# The port to bind to.
PORT = 30025

# UTC.
UTC = datetime.timezone.utc

# A rough location for the MOO's setting, San Francisco.
LOCATION = api.wgs84.latlon(37.7775, -122.416389, 16)

ts = api.load.timescale()
ephemeris = api.load(EPHEMERIS_DATA)


def get_prev_next(time, data):
    prev_event = None
    prev_event_delta = None
    next_event = None
    next_event_delta = None

    # Convert to UTC time.
    data = ((d[0].astimezone(UTC), *(d[1:])) for d in data)

    for event in data:
        t = event[0].astimezone(UTC)
        delta = abs(t - time)

        if t <= time:
            if prev_event is None or delta < prev_event_delta:
                prev_event = event
                prev_event_delta = delta
        elif t > time:
            if next_event is None or delta < next_event_delta:
                next_event = event
                next_event_delta = delta

    return (prev_event, next_event)


def sunrise_sunset(time=None, location=LOCATION):
    if (time is None):
        time = datetime.datetime.now(UTC)

    # Search within 5 days in either direction.
    # This is probably overkill.
    delta = datetime.timedelta(days=5)
    low_time = ts.from_datetime(time - delta)
    high_time = ts.from_datetime(time + delta)

    f = almanac.sunrise_sunset(ephemeris, location)

    events = almanac.find_discrete(low_time, high_time, f)

    rises = get_prev_next(time, (event for event in zip(*events) if event[1]))
    sets = get_prev_next(time, (event for event in zip(*events) if not event[1]))

    for event in itertools.chain(rises, sets):
        if event is None:
            raise ValueError("Couldn't find a past/future sunrise/sunset")

    rises = [d[0] for d in rises]
    sets = [d[0] for d in sets]

    return (rises, sets)


def body_rise_set(time=None, body=None, location=LOCATION):
    if (time is None):
        time = datetime.datetime.now(UTC)
    if (body is None):
        body = ephemeris['Moon']

    # Search within 5 days in either direction.
    # This is probably overkill.
    delta = datetime.timedelta(days=5)
    low_time = ts.from_datetime(time - delta)
    high_time = ts.from_datetime(time + delta)

    f = almanac.risings_and_settings(ephemeris, body, location)

    events = almanac.find_discrete(low_time, high_time, f)

    rises = get_prev_next(time, (event for event in zip(*events) if event[1]))
    sets = get_prev_next(time, (event for event in zip(*events) if not event[1]))

    for event in itertools.chain(rises, sets):
        if event is None:
            raise ValueError("Couldn't find a past/future body rise/set")

    rises = [d[0] for d in rises]
    sets = [d[0] for d in sets]

    return (rises, sets)


def lunar_eclipses(time=None):
    if (time is None):
        time = datetime.datetime.now(UTC)

    # Search within 20 years or so.
    # If we somehow don't find a lunar eclipse, we can error later.
    delta = datetime.timedelta(days=10*365)
    low_time = ts.from_datetime(time - delta)
    high_time = ts.from_datetime(time + delta)

    times, etype, details = eclipselib.lunar_eclipses(low_time, high_time, ephemeris)

    eclipses = get_prev_next(time, zip(times, etype))

    for event in eclipses:
        if event is None:
            raise ValueError("Couldn't find a past/future lunar eclipse")

    return eclipses


def nearest_lunar_eclipse(time=None):
    if (time is None):
        time = datetime.datetime.now(UTC)

    # Search within 10 years or so.
    # If we somehow don't find a lunar eclipse, we can error later.
    delta = datetime.timedelta(days=5*365)

    low_time = ts.from_datetime(time - delta)
    high_time = ts.from_datetime(time + delta)

    times, etype, details = eclipselib.lunar_eclipses(low_time, high_time, ephemeris)

    if getattr(times.tt, 'size', -1) < 1:
        raise ValueError('No lunar eclipses in range')

    # Convert to datetimes.
    times = times.astimezone(UTC)

    # Find the closest eclipse.
    closest = None
    closestdelta = None

    for t, et in zip(times, etype):
        delta = abs(t - time)
        if closest is None or delta < closestdelta:
            closest = (t, et)
            closestdelta = delta

    return closest


def real_time(mootime):
    moorawtime = mootime.replace(year=mootime.year - 259)

    moosecs = moorawtime.timestamp()

    realsecs = moosecs / 8 + 1620903200

    realtime = datetime.datetime.fromtimestamp(realsecs, tz=UTC)

    return realtime


def moo_time(realtime=None):
    if (realtime is None):
        realtime = datetime.datetime.now(UTC)

    realsecs = realtime.timestamp()

    moosecs = (realsecs - 1620903200) * 8

    moorawtime = datetime.datetime.fromtimestamp(moosecs, tz=UTC)

    mootime = moorawtime.replace(year=moorawtime.year + 259)

    return mootime


async def request_handler(reader, writer):
    addr = writer.get_extra_info('peername')

    request = await reader.readline()

    reply = ''

    try:
        request = request.decode().strip()

        print(f'Got request from {addr!r}: {request!r}')

        if (request == 'MoonPhaseReal'):
            phase = almanac.moon_phase(ephemeris, ts.now())

            reply = f'{phase.degrees:.10f}'
        elif (request == 'MoonPhaseMOO'):
            mootime = ts.from_datetime(moo_time())
            phase = almanac.moon_phase(ephemeris, mootime)

            reply = f'{phase.degrees:.10f}'
        elif (request == 'NearestLunarEclipseReal'):
            time, etype = nearest_lunar_eclipse()
            etype = eclipselib.LUNAR_ECLIPSES[etype]
            time = round(time.timestamp())

            reply = f'{time}\n{etype}'
        elif (request == 'NearestLunarEclipseMOO'):
            time, etype = nearest_lunar_eclipse(moo_time())
            etype = eclipselib.LUNAR_ECLIPSES[etype]
            time = round(real_time(time).timestamp())

            reply = f'{time}\n{etype}'
        elif (request == 'LunarEclipsesReal'):
            past, future = lunar_eclipses()

            past = (round(past[0].timestamp()), eclipselib.LUNAR_ECLIPSES[past[1]])
            future = (round(future[0].timestamp()), eclipselib.LUNAR_ECLIPSES[future[1]])

            reply = f'{past[0]}\n{past[1]}\n{future[0]}\n{future[1]}'
        elif (request == 'LunarEclipsesMOO'):
            past, future = lunar_eclipses(moo_time())

            past = (round(real_time(past[0]).timestamp()), eclipselib.LUNAR_ECLIPSES[past[1]])
            future = (round(real_time(future[0]).timestamp()), eclipselib.LUNAR_ECLIPSES[future[1]])

            reply = f'{past[0]}\n{past[1]}\n{future[0]}\n{future[1]}'
        elif (request == 'SunRiseSetReal'):
            rises, sets = sunrise_sunset()
            data = (f'{round(t.timestamp())}' for t in itertools.chain(rises, sets))

            reply = '\n'.join(data)
        elif (request == 'SunRiseSetMOO'):
            rises, sets = sunrise_sunset(moo_time())
            data = (f'{round(real_time(t).timestamp())}' for t in itertools.chain(rises, sets))

            reply = '\n'.join(data)
        elif (request == 'MoonRiseSetReal'):
            rises, sets = body_rise_set()
            data = (f'{round(t.timestamp())}' for t in itertools.chain(rises, sets))

            reply = '\n'.join(data)
        elif (request == 'MoonRiseSetMOO'):
            rises, sets = body_rise_set(moo_time())
            data = (f'{round(real_time(t).timestamp())}' for t in itertools.chain(rises, sets))

            reply = '\n'.join(data)
        else:
            reply = 'UnknownCommand'

    except UnicodeError as err:
        print(f'Failed to decode request from {addr!r}: {err}')
        reply = 'BadCommand'

    except ValueError as err:
        print(f'Failed to handle request from {addr!r}: {err}')
        reply = 'BadValue'

    # Add a terminator.
    reply = reply + '\n.\n'
    replydata = reply.encode('ascii')

    print(f'Sending reply to {addr!r}: {reply!r}')

    writer.write(replydata)
    await writer.drain()

    writer.close()


async def main():
    server = await asyncio.start_server(request_handler, port=PORT)

    addrs = ', '.join(str(sock.getsockname()) for sock in server.sockets)
    print(f'Listening on {addrs}')

    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    print(f'Running in {os.getcwd()}...')
    asyncio.run(main())
