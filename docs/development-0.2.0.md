# modstride 0.2.0 development report

The Field Counter example ports an original Fabric mod from Minecraft 1.20.4 to 1.20.6 with Mojang mappings. Right-click uses the held stack's own counter and displays its new value on the logical server. The migration keeps the registry ID and the integer key. It replaces the removed `ItemStack.getTag()` and `getOrCreateTag()` calls with reads from `DataComponents.CUSTOM_DATA` and writes through `CustomData.update`. That API updates the custom-data component while preserving other keys. The Java rule recognizes only the exact reviewed helper. A different helper is deferred for review.

Minecraft 1.20.5 introduced item data components and Java 21. The pinned 1.20.6 Mojang-mapped JAR exposes `CustomData.EMPTY`, `copyTag()` and the static update method with the component type, stack and tag consumer. A 1.20.6 build with just the configuration edits failed with two `cannot find symbol` errors for the old methods. The CLI port applied the Java rule and two configuration rules and produced the target JAR. [Mojang release notes](https://www.minecraft.net/en-us/article/minecraft-java-edition-1-20-5) · [Fabric porting notes](https://fabricmc.net/2024/04/19/1205.html) · [NeoForge item-data primer](https://github.com/neoforged/.github/blob/main/primers/1.20.5/index.md)

## Reproduce

Use Python 3.11+, Gradle 8.7, a JDK 17 for the baseline and JDK 21 for the target. The sample pins Loom 1.6.12, Loader 0.15.11, and a version-matched Fabric API. From the repository root:

```text
python -m pip install .
modstride plan examples/counter-source-mod --to-version 1.20.6 --to-loader fabric --output-dir work/field-plan
modstride apply --plan work/field-plan/migration-plan.json --workspace work/field-port --dry-run
modstride apply --plan work/field-plan/migration-plan.json --workspace work/field-port
```

Make a disposable byte-for-byte copy of `examples/counter-source-mod` at `work/field-baseline`. For example, in PowerShell use `Copy-Item -LiteralPath examples/counter-source-mod -Destination work/field-baseline -Recurse`. Set `JAVA_HOME` to JDK 21 and provide an absolute JDK 17 path for the baseline. The CLI compares the baseline files against the hashes captured during apply and requires separate directories.

```text
modstride verify --workspace work/field-port --run-gradle --timeout 180 --parity-task counterParity --baseline work/field-baseline --baseline-java "PATH_TO_JDK_17"
modstride report --workspace work/field-port
```

For client startup, create `run/client/options.txt` in the disposable project containing `onboardAccessibility:false` so the first-run screen does not hold the smoke test open. On a graphical machine, add `--client-ready MODSTRIDE_COUNTER_CLIENT_READY` to the verify command. The fixture waits for the title screen and completed resource load, checks its item is registered, logs the marker and closes the client. The baseline can be launched separately with JDK 17 using `gradle -p work/field-baseline --no-daemon --console=plain runClient` after the same options setup.

For dedicated-server startup, review and accept Minecraft's EULA yourself before supplying `run/server/eula.txt` in the disposable target and adding `--server-ready MODSTRIDE_COUNTER_SERVER_READY`. The fixture checks its item after the dedicated server reaches its first tick, writes its marker and halts. modstride records a blocked stage if the file is absent. [Minecraft server setup](https://help.minecraft.net/hc/en-us/articles/360058525452)

## Observed behavior

The Windows run used Gradle 8.7, Temurin 17.0.21 for the original, and Temurin 21.0.13 for the port. Both builds and both development-client readiness probes passed. The target's dedicated-server stage was blocked because the disposable server directory lacked an operator-accepted EULA file. The verification command returned exit code 1 for that blocked stage and retained the successful checks. Gradle's ordinary unit-test task reported `NO-SOURCE`. The behavior checks ran through the separate `counterParity` task.

The migrated artifact was `build/libs/field-counter-1.0.0.jar`, SHA-256 `cb28ce9fea8ba1afafddcf6ef9867dccbf9a4f1a73c03f02c8e9295df803d7ae`. The verification JSON records both parity logs, the client readiness log, the Gradle build log, and their hashes.

The paired task bootstraps Minecraft in each version, runs the same counter logic on real ItemStacks and compares the emitted integers. Each probe also asserts the expected value. This covers default state, repeated increments, isolation between stacks, copy behavior and an ItemStack codec round trip within each version.

| Observation | 1.20.4 | 1.20.6 |
| --- | ---: | ---: |
| New stack | 0 | 0 |
| First use logic | 1 | 1 |
| Second use logic | 2 | 2 |
| Independent stack | 0 | 0 |
| Stack copy | 2 | 2 |
| Reload through the version's codec | 2 | 2 |
| Increment after reload | 3 | 3 |

The probes call the increment logic directly. A real player interaction, the rendered action-bar text, client/server synchronization and opening an upgraded world still require in-game tests. Runtime checks exercise the Loom development client. A built JAR has separate packaging evidence. An actual Forge 1.12.2 → NeoForge 1.21.1 port remains experimental. [Feasibility assessment](forge-1122-neoforge-1211.md)

## Project checks

On Windows, the Python 3.11 suite passed 45 tests and skipped one symlink test because the account lacked symlink privileges. Ruff lint and format checks, the five-rule catalogue and target profile validation, and the official Agent Skills validator passed. The 0.2.0 wheel installed into a separate Python 3.14 environment and read the saved migration state and evidence.
