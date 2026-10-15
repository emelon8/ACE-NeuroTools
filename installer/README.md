# Lab GUI pilot environments

The human-maintained `environment.yml` contains the runtime dependencies only.
`conda-lock.yml` resolves Windows x86-64, Intel Mac, Apple silicon Mac, and Linux.
The platform subdirectories contain generated, version/build-pinned environment
specifications that the Miniforge-based setup script can install without asking
labmates to install conda-lock. Pip entries retain their distribution hashes.
Conda still validates these specifications with its solver at installation time.

`virtual-packages.yml` records the target operating-system minimums and excludes
CUDA from this CPU-based pilot. It does not change a user's operating system or
force unsupported packages onto their computer.

Regenerate from the repository root using conda-lock and a Conda executable:

```bash
conda-lock lock --conda conda -f installer/environment.yml \
  --lockfile installer/conda-lock.yml \
  --virtual-package-spec installer/virtual-packages.yml \
  -p win-64 -p osx-64 -p osx-arm64 -p linux-64
conda-lock render -k env \
  --filename-template 'installer/{platform}/environment' installer/conda-lock.yml
```

Using micromamba 2.6 to solve foreign Mac platforms on Linux can incorrectly
interpret conda-lock's empty `CONDA_OVERRIDE_OSX` as version zero. Use Conda for
that regeneration, or a solver wrapper that sets `CONDA_OVERRIDE_OSX=11.0` for
the two Mac targets after conda-lock prepares the subprocess environment.

Before sharing a pilot ZIP, require the three **Lab GUI installation** CI jobs
to pass. They run the same setup command as users, from a checkout with spaces
in its path, test movie reading and GUI HTTP resources, and execute the generated
launcher from another working directory. Then have a labmate confirm native
file picking, recording preview, short-recording analysis, cancellation, and
reopening after an OS restart. Hosted checks cannot exercise Finder/Gatekeeper
approval or establish scientific validity on lab recordings.

The runtime lock is separate from the full development/CI lock at the repository
root. Update both when changing shared scientific dependencies.
