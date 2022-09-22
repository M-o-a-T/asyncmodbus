#!/usr/bin/env python3
"""
Basic tool support

"""
import asyncclick as click
import struct
import anyio
from getopt import getopt

from moat.modbus.types import Coils,DiscreteInputs,HoldingRegisters,InputRegisters
from moat.modbus.types import IntValue,LongValue,SwappedLongValue,SignedIntValue,SignedLongValue,SwappedSignedLongValue,FloatValue,SwappedFloatValue,DoubleValue,SwappedDoubleValue,SignedQuadValue,QuadValue,SwappedQuadValue,SwappedSignedQuadValue

map_kind = {'c':Coils,'d':DiscreteInputs,'h':HoldingRegisters,'i':InputRegisters}
map_type = {
        'raw': IntValue,
        'u1': IntValue,
        'U1': IntValue,
        'u2': LongValue,
        'U2': SwappedLongValue,
        'u4': QuadValue,
        'U4': SwappedQuadValue,
        's1': SignedIntValue,
        'S1': SignedIntValue,
        's2': SignedLongValue,
        'S2': SwappedSignedLongValue,
        's4': SignedQuadValue,
        'S4': SwappedSignedQuadValue,
        'f2': FloatValue,
        'F2': SwappedFloatValue,
        'f4': DoubleValue,
        'F4': SwappedDoubleValue,
        }

import logging
FORMAT = ('%(asctime)-15s %(threadName)-15s '
          '%(levelname)-8s %(module)-15s:%(lineno)-8s %(message)s')
logging.basicConfig(format=FORMAT)
log = logging.getLogger()
log.setLevel(logging.WARN)


@click.group()
async def main():
    pass


UNIT = 0x1

def get_len(typ):
    if typ in {"r","raw"}:
        return 1
    return int(typ[1:])

def _doc(v):
    return v.__doc__.split("\n")[0]
_args_kind="\n".join(f"{k :3s}  {_doc(v)}" for k,v in map_kind.items())
_args_type="\n".join(f"{k :3s}  {_doc(v)}" for k,v in map_type.items())
_args_help=f"""\
\b
Setting values:
-u UNIT   register to this unit; default 1
-k KIND   use this register range, default Input
-t TYPE   register this datatype, default Raw
-r REGNUM start at this register, default 0, auto-incremented
-n COUNT  register this many variables, default 1
-v VALUE  set the register(s) to this value

\b
Kinds:
{_args_kind}

\b
Types:
{_args_type}
"""

@main.command(context_settings=dict(
        show_default=True,
        ignore_unknown_options=True,
        help_option_names=["-?","--help"],
    ), epilog=_args_help,
)
@click.option('--host','-s', default="localhost", help="host to bind to")
@click.option('--port','-p', type=int, default=502, help="port to bind to")
@click.option('--debug','-d', is_flag=True, help="Log debug messages")
@click.argument('args', nargs=-1, type=click.UNPROCESSED)
async def server(host, port, debug, args):
    """
    Basic Modbus server, for static tests.
    """
    if debug:
        log.setLevel(logging.DEBUG)
    if not args:
        click.UsageError("You didn't add any values to serve")

    from moat.modbus.server import ModbusServer
    s = ModbusServer(address=host, port=port)
    unit=None
    kind=InputRegisters
    typ=IntValue
    num=1
    reg=0

    kv,a = getopt(args, "u:k:t:r:n:v:",
            "--unit= --kind= --type= reg= register= num= val= value=".split())
    if a:
        raise click.UsageError(f"Unknown argument: {' ' .join(a)}")
    for k,v in kv:
        pend=True
        if k in ("-u","--unit"):
            unit = s.add_unit(int(v))
        elif k in ("-k", "--kind"):
            kind = map_kind[v[0]]
        elif k in ("-t", "--type"):
            typ = map_type[v[0]]
        elif k in ("-r", "--reg", "--register"):
            reg = int(v)
        elif k in ("-n", "--num"):
            num=int(v)
        elif k in ("-v", "--val", "--value"):
            try:
                v=int(v)
            except ValueError:
                v=float(v)
            if unit is None:
                unit = s.add_unit(int(1))
            for _ in range(num):
                unit.add(kind,reg,typ(v))
                reg += typ.len
            pend=False
        else:
            raise click.UsageError(f"Unknown argument: {k !r}")
    if pend:
        raise click.UsageError(f"Values must be at the end")

    await s.serve()


def flint(v):
    try:
        return int(v)
    except ValueError:
        return float(v)

@main.command(context_settings=dict(show_default=True))
@click.option('--host','-h', default="localhost", help="destination host")
@click.option('--port','-p', type=int, default=502, help="destination port")
@click.option('--unit','-u', type=int, default=1, help="unit to query")
@click.option('--kind','-k', default="i", help="query type: input, discrete, hold, coil")
@click.option('--start','-s', default=0, help="starting register")
@click.option('--num','-n', type=int, default=1, help="number of values")
@click.option('--type','-t', default="raw", help="value type: s1,s2,s4,u1,u2,u4,f2,f4,raw; Sx/Fx=swapped")
@click.option('--debug','-d', is_flag=True, help="Log debug messages")
@click.argument('values', nargs=-1)
async def client(host, port, unit, kind, start, num, type, values, debug):
    """
    Basic Modbus-TCP client.
    """
    if debug:
        log.setLevel(logging.DEBUG)

    from moat.modbus.client import ModbusClient
    async with ModbusClient() as g:
        h = g.host(host,port)
        u = h.unit(unit)
        s = u.slot("default")

        k = map_kind[kind[0]]
        t = map_type[type]
        if values:
            if len(values) == 1:
                values = values*num
            elif len(values) != num:
                raise click.UsageError("One or N values!")
        for i in range(num):
            v = s.add(k,start,t)
            if values:
                v.value = flint(values[i])
            start += t.len
            num -= 1

        try:
            if values:
                await s.setValues()
            else:
                res = await s.getValues()
                print(res)
        except Exception as exc:
            log.exception(f"Problem:{repr(exc)}")


if __name__ == "__main__":
    main(_anyio_backend="trio")