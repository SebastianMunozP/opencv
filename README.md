# Module opencv 

Provide a description of the purpose of the module and any relevant information.

## Model viam:opencv:chessboard

Provide a description of the model and any relevant information.

### Configuration
The following attribute template can be used to configure this model:

```json
{
"attribute_1": <float>,
"attribute_2": <string>
}
```

#### Attributes

The following attributes are available for this model:

| Name          | Type   | Inclusion | Description                |
|---------------|--------|-----------|----------------------------|
| `camera_name` | string  | Required  | Name of the camera used for checking pose of chessboard. |
| `pattern_size` | list | Required  | Size of the chessboard pattern. |
| `square_size_mm` | int | Required  | Physical size of a square in the chessboard pattern.  |

#### Example Configuration

```json
{
  "camera_name": "cam",
  "pattern_size": [9, 6],
  "square_size_mm": 21
}
```