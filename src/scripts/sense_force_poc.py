import argparse
import asyncio
import os

from dotenv import load_dotenv
from viam.robot.client import RobotClient
from viam.components.arm import Arm

from typing import Optional


async def connect():
    load_dotenv()
    opts = RobotClient.Options.with_api_key( 
        api_key=os.getenv('VIAM_MACHINE_API_KEY'),
        api_key_id=os.getenv('VIAM_MACHINE_API_KEY_ID'),
    )
    address = os.getenv('VIAM_MACHINE_ADDRESS')
    return await RobotClient.at_address(address, opts)


async def main(
    arm_name: str,
):
    machine: Optional[RobotClient] = None
    arm: Optional[Arm] = None

    try:
        machine = await connect()
        arm = Arm.from_robot(machine, arm_name)
        resp = await arm.do_command({"get_tcp_forces_tool": ""})
        print(resp)
    except Exception as e:
        print("Caught exception in script main: ")
        raise e
    finally:
        if arm:
            await arm.close()
        if machine:
            await machine.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Sense force poc script')
    parser.add_argument(
        '--arm-name',
        type=str,
        required=True,
        help='Name of the arm component'
    )

    args = parser.parse_args()
    asyncio.run(main(arm_name=args.arm_name))
