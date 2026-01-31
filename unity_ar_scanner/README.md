# ReimagineAI Unity AR Scanner

This Unity project provides AR room scanning capabilities for the ReimagineAI Flutter app using AR Foundation.

## Requirements

- Unity 2022.3 LTS or later (2023.x recommended)
- AR Foundation 6.x
- ARKit XR Plugin (for iOS)
- ARCore XR Plugin (for Android)

## Setup Instructions

### 1. Open in Unity

1. Open Unity Hub
2. Click "Add" and select this folder (`unity_ar_scanner`)
3. Open the project with Unity 2022.3 LTS or later

### 2. Install Packages

The `Packages/manifest.json` already includes required packages. Unity will install them automatically.

If packages fail to install:
1. Window → Package Manager
2. Add the following packages:
   - AR Foundation
   - ARKit XR Plugin  
   - ARCore XR Plugin
   - XR Plugin Management

### 3. Configure XR Settings

1. Edit → Project Settings → XR Plug-in Management
2. Enable "ARCore" for Android tab
3. Enable "ARKit" for iOS tab

### 4. Create Scenes

Create two scenes in `Assets/Scenes/`:

#### RoomScanner Scene
1. Create new scene: File → New Scene
2. Add AR Session Origin:
   - Right-click in Hierarchy → XR → AR Session
   - Right-click in Hierarchy → XR → AR Session Origin (or XR Origin)
3. Add AR Mesh Manager to AR Session Origin:
   - Select AR Session Origin
   - Add Component → AR Mesh Manager
   - Create a Mesh Prefab (see below) and assign it
4. Add the RoomScannerController script to a new GameObject
5. Add the MeshExporter script
6. Add the FlutterBridge script

#### RoomViewer Scene
1. Create new scene
2. Add a Camera
3. Add a Light (Directional)
4. Create empty GameObject "RoomContainer"
5. Add RoomViewerController script
6. Add MaterialEditor script
7. Add FlutterBridge script (DontDestroyOnLoad, so may already exist)

### 5. Create Mesh Prefab

1. Create new empty GameObject
2. Add components:
   - MeshFilter
   - MeshRenderer (with a default material)
   - MeshCollider
3. Drag to Assets/Prefabs to create prefab
4. Assign to ARMeshManager's "Mesh Prefab" field

### 6. Build for Flutter Integration

#### Android Export
1. File → Build Settings → Android
2. Switch Platform to Android
3. Player Settings:
   - Set minimum API level to 26
   - Enable IL2CPP scripting backend
   - Set Architecture to ARM64
4. Click "Export" (not Build)
5. Export to: `../mobile/android/unityLibrary/`

#### iOS Export
1. File → Build Settings → iOS
2. Switch Platform to iOS
3. Player Settings:
   - Set minimum iOS version to 14.0
   - Enable "Requires ARKit support"
4. Click "Export"
5. Export to: `../mobile/ios/UnityExport/`

## Flutter Integration

After exporting, follow the flutter_unity_widget setup:

### Android
1. Add to `mobile/android/settings.gradle`:
```gradle
include ':unityLibrary'
project(':unityLibrary').projectDir = file('./unityLibrary')
```

2. Add to `mobile/android/app/build.gradle` dependencies:
```gradle
implementation project(':unityLibrary')
```

### iOS
1. Open `mobile/ios/Runner.xcworkspace` in Xcode
2. Drag UnityExport folder into the project
3. Add Unity framework to "Frameworks, Libraries, and Embedded Content"

## Scripts Overview

### FlutterBridge.cs
Handles bidirectional communication between Flutter and Unity.

**Messages from Flutter:**
- `startScan` - Start AR room scanning
- `stopScan` - Stop scanning
- `exportRoom` - Export scanned mesh to GLB file
- `loadRoom` - Load a GLB/OBJ file for viewing
- `editMaterial` - Apply material edit (JSON with target, property, value)
- `selectPart` - Select a room part by name

**Messages to Flutter:**
- `scanProgress` - Scanning progress (0-1)
- `roomExported` - Path to exported GLB file
- `partSelected` - Name of selected part
- `editApplied` - Confirmation of material edit
- `error` - Error message

### RoomScannerController.cs
Manages AR mesh scanning using ARMeshManager.

### MeshExporter.cs
Exports Unity meshes to GLB (binary glTF) format.

### RoomViewerController.cs
Provides 3D viewing with orbit camera and part selection.

### MaterialEditor.cs
Applies color, texture, and material changes to room parts.

## Supported Edit Commands

Material edits are sent as JSON:
```json
{
  "target": "wall",      // wall, floor, ceiling, furniture, door, window, all
  "property": "color",   // color, texture, material
  "value": "#FF5733"     // hex color, URL, base64, or preset name
}
```

### Named Colors
white, black, red, green, blue, yellow, cyan, magenta, gray, navy, beige, cream, brown, tan, olive, teal, coral, salmon, lavender, mint, peach

### Material Presets
wood, hardwood, marble, stone, metal, steel, glass

## Troubleshooting

### AR not working on device
- Ensure ARKit/ARCore is enabled in XR settings
- Check camera permissions
- Verify device supports AR (LiDAR for best mesh quality on iOS)

### Mesh not generating
- ARMeshManager needs LiDAR on iOS for good mesh
- On Android, depth is estimated which may not produce mesh on all devices
- Try scanning slowly and ensure good lighting

### GLB export issues
- Check Application.persistentDataPath has write permissions
- Verify mesh has vertices before export

### Flutter communication not working
- Ensure FlutterBridge GameObject exists in scene
- Check unity_widget is properly receiving/sending messages
- Verify JSON message format matches expected structure
