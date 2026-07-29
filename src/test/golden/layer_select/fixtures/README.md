# `layer_select` golden fixtures

Multi-layer EXR is required for layer-selection scenarios (`sourceMedia()` layer names).

## Generate a test file (recommended for devs)

```bash
cd src/test/golden/layer_select/fixtures
./regenerate_layers_fixture.sh   # needs oiiotool — brew install openimageio
export LAYER_EXR_FIXTURE="$PWD/test_layers.exr"
```

That creates `test_layers.exr` with three parts named `beauty`, `diffuse`, and `specular`.

## Or use your own file

```bash
export LAYER_EXR_FIXTURE=/path/to/any/multilayer.exr
```

Optional gitignored env file:

```bash
echo "LAYER_EXR_FIXTURE=$PWD/test_layers.exr" >> layers.env
```

## Scenarios

| Scenario | Fixture |
|---|---|
| `ls_activate`, `ls_activate_shortcut`, `ls_activate_menu`, `ls_no_layers` | none (movieproc) |
| all other `ls_*` scenarios | `LAYER_EXR_FIXTURE` |

Set the variable directly — copying `layers.env.example` is optional:

```bash
export LAYER_EXR_FIXTURE=/path/to/multi_layer.exr
```
