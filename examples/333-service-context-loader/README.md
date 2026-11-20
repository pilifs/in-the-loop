# A service chosen by the thread context loader

The application and both context loaders share a provider-free parent that defines the service API and construction log. Each child defines its own providers from the compiled fixture bytes and gives the real ServiceLoader one byte-backed resource descriptor. A second call changes only the thread context and creates a fresh ServiceLoader.

[Loader and descriptor definitions](both/styles/World.java) · [Independent ordering and laziness oracle](controls/oracle.py)
