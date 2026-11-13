# Installation

Use Python 3.11 or newer. From a checkout or source archive, create a virtual environment and install the local package.

| Platform | Create and install |
| --- | --- |
| Windows PowerShell | `py -3 -m venv .venv` then `./.venv/Scripts/python.exe -m pip install .` |
| Linux or macOS | `python3 -m venv .venv` then `./.venv/bin/python -m pip install .` |

Activate the environment, or invoke `modstride.exe` under `.venv/Scripts` on Windows and `modstride` under `.venv/bin` on Unix. Verify with `modstride --version`. If you have a wheel, pass the wheel filename to pip in place of the dot. For development, install with `python -m pip install -e ".[dev]"`.

The CLI uses the standard library at runtime. Python packaging tools may need network access for the build backend. An existing wheel installs without resolving external runtime dependencies.

To build the original sample, use JDK 17 and Gradle 8.7. For other projects, review their Gradle wrapper, declared toolchain, loader and plugin support. A checked-in wrapper is used when present. You can pass an absolute Gradle executable path with `--gradle` when you opt into build execution. [Gradle compatibility](https://docs.gradle.org/current/userguide/compatibility.html)

For the skill, use the documented project directory for your agent or install a standalone skill archive. [Agent installation](agents.md)
