
from .figlet_title import makeFigletBanner


def printBanner(config:list) -> None:
    title = makeFigletBanner(config[1]["name"])
    title += "\n\n"
    title += f"[*]  Powered:\t{config[1]['vendor']}\n"
    title += f"[*]  Version:\t{config[1]['version']}\n"
    title += "\n"
    print(title)
    