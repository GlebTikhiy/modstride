# Copper Token from Fabric 1.20.1 to Fabric 1.20.4

Copper Token is an original MIT-licensed example with one registered item, a translated name, and a model that references the game's copper ingot texture by identifier. The repository includes the source and metadata. Loom obtains the game and official mappings from the upstream distribution during build setup.

From the repository root, with modstride installed:

```text
modstride scan examples/sample-source-mod
modstride plan examples/sample-source-mod --to-version 1.20.4 --to-loader fabric --output-dir work/plan
modstride apply --plan work/plan/migration-plan.json --workspace work/target --dry-run
modstride apply --plan work/plan/migration-plan.json --workspace work/target
modstride resume --workspace work/target
modstride verify --workspace work/target
modstride report --workspace work/target
```

The plan matches two deterministic rules for this layout. The rules change the literal Minecraft version in `gradle.properties` and the exact Minecraft dependency in `fabric.mod.json`. Review the remaining plan operations for registry calls, item behavior, resources, and compatibility. The example retains its registration code, item identifier, stack limit and asset identifiers.

## Build reproduction

Use JDK 17 and Gradle 8.7. The example pins Fabric Loom 1.6.12 and Fabric Loader 0.15.11. Review the sample build scripts and Gradle launcher before enabling execution. Gradle can download build tooling, Minecraft and its dependencies.

```text
modstride verify --workspace work/target --run-gradle --timeout 600
modstride report --workspace work/target
```

If Gradle is outside `PATH`, add `--gradle` with the full launcher path, quoting spaces. The Windows launcher is `gradle.bat`. Successful build output is normally at `work/target/build/libs/copper-token-1.0.0.jar`. Build evidence includes the Gradle log and discovered artifact SHA-256.

On Windows 11 with Temurin 17.0.21 and Gradle 8.7, both a clean source build and the CLI-produced target build executed `:compileJava` and `:remapJar` successfully. Gradle reported `:test NO-SOURCE` for both. The target JAR contained the compiled class and MIT notice and had SHA-256 `cd61c5c6e4cd43198bd93f305a75bc9eafff33d5e031943d7168fd045af841d4`. Client launch, dedicated server launch and gameplay parity remain unverified.

## Gameplay parity checklist

Run the original and target builds in separate, disposable instances using the corresponding Minecraft and Fabric Loader versions.

For the dedicated-server check, follow the Minecraft server setup instructions, including its EULA acceptance step. [Minecraft server setup](https://help.minecraft.net/hc/en-us/articles/360058525452)

1. Confirm both clients load the mod and create a disposable creative world with commands enabled.
2. Run `/give @s modstride_example:copper_token 17` with an empty inventory. Check the identifier, one 16-item stack, and one single item.
3. Check the inventory tooltip says **Copper Token** in English (US) and the item renders with the copper ingot appearance.
4. Save and reload each disposable world. Verify the stacks and identifier still match.
5. Repeat the command on a disposable dedicated server with a matching client, then reconnect to verify that the inventory is synchronized.

Record the game and loader versions, commands, actual observations, and a log or note in the target workspace. To import evidence, pass `--evidence PATH` to `modstride verify`. The JSON file maps `dedicated-server`, `client`, or `gameplay` to an object with `status`, `detail`, and a workspace-relative `path` to a nonempty evidence file. The report identifies these results as external evidence.
