"""Compatibility entry point for the calcium imaging pipeline."""

from aceneurotools.pipelines import calcium_imaging as _implementation
from aceneurotools.pipelines.calcium_imaging import CalciumImagingPipeline, MiniscopePipeline, main

__all__ = ["CalciumImagingPipeline", "MiniscopePipeline", "main"]


def __getattr__(name):
    return getattr(_implementation, name)


if __name__ == "__main__":
    main()
