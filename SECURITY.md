# Security

Report suspected vulnerabilities through GitHub private vulnerability reporting when enabled for the public repository. If private reporting is unavailable, contact a maintainer through a private channel before sharing reproduction details.

Include the modstride version, platform, input shape, and a minimal reproduction. Remove access tokens, personal paths, and third-party source you lack permission to share.

Static scanning reads bounded metadata and class headers. It never executes a JAR or extracts archive contents. Gradle verification executes project-supplied build logic with the current process's permissions. Review build scripts, wrappers and dependency sources first. Use an isolated environment for projects you do not trust. Run gameplay checks only against disposable worlds or backups.

Review external rule catalogues before passing them to the CLI. Reports can include absolute paths and logs that contain local environment information. Review them before attaching to an issue.
