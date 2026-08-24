/// API Configuration for ReimagineAI
class ApiConfig {
  /// Override at build time, e.g.:
  /// `flutter build web --dart-define=API_BASE_URL=https://api.example.com`
  /// `flutter build appbundle --dart-define=API_BASE_URL=http://62.238.120.111:8100`
  static const String baseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://127.0.0.1:8100',
  );
  
  static const String apiVersion = '/api/v1';
  
  // Auth Endpoints
  static const String login = '$apiVersion/auth/login';
  static const String signup = '$apiVersion/auth/signup';
  static const String logout = '$apiVersion/auth/logout';
  static const String me = '$apiVersion/auth/me';
  
  // Chat Endpoints
  static const String chat = '$apiVersion/chat/';
  static const String chatWithImage = '$apiVersion/chat/with-image';
  static const String conversations = '$apiVersion/chat/conversations';
  
  // Image Endpoints
  static const String generateImages = '$apiVersion/images/generate';
  static const String analyzeRoom = '$apiVersion/images/analyze';
  static const String redesignRoom = '$apiVersion/images/redesign';
  
  // Room/3D Scanning Endpoints (Legacy - Unity-based)
  static const String rooms = '$apiVersion/rooms';
  static const String roomUpload = '$apiVersion/rooms/upload';
  static String roomById(String id) => '$apiVersion/rooms/$id';
  static String roomEdit(String id) => '$apiVersion/rooms/$id/edit';
  static String roomGenerateTexture(String id) => '$apiVersion/rooms/$id/generate-texture';
  
  // Depth/3D Mesh Endpoints (Photo-based)
  static const String depthGenerateMesh = '$apiVersion/depth/generate-mesh';
  static const String depthGenerateMeshUpload = '$apiVersion/depth/generate-mesh/upload';
  static const String depthMeshes = '$apiVersion/depth/meshes';
  static String depthMesh(String meshId) => '$apiVersion/depth/mesh/$meshId';
  static String depthMeshInfo(String meshId) => '$apiVersion/depth/mesh/$meshId/info';
  static const String depthUpdateMesh = '$apiVersion/depth/update-mesh';
  
  // Editable 3D Scene Endpoints (structured room + furniture objects)
  static const String scenes = '$apiVersion/scenes';
  static const String sceneCatalog = '$apiVersion/scenes/catalog';
  static const String sceneGenerate = '$apiVersion/scenes/generate';
  static const String sceneGenerateUpload = '$apiVersion/scenes/generate/upload';
  static String sceneById(String id) => '$apiVersion/scenes/$id';
  static String sceneOps(String id) => '$apiVersion/scenes/$id/ops';
  static String sceneNlEdit(String id) => '$apiVersion/scenes/$id/nl-edit';
  static String sceneVersions(String id) => '$apiVersion/scenes/$id/versions';
  static String sceneRevert(String id, int version) =>
      '$apiVersion/scenes/$id/revert/$version';
  static String sceneEnhance(String id) => '$apiVersion/scenes/$id/enhance';

  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 120); // Normal operations
  static const Duration longReceiveTimeout = Duration(minutes: 10); // Heavy operations (mesh, AI)
}
