"""WebSocket core package.

Avoid importing runtime-heavy modules here. Import concrete components from
their submodules so package import stays side-effect free.
"""

__all__: list[str] = []
