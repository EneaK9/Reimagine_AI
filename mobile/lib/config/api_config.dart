/// API Configuration for ReimagineAI
class ApiConfig {
  // Your computer's IP - change this if your IP changes
  static const String baseUrl = 'http://192.168.0.252:8000';
  
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
  
  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 15);
  static const Duration receiveTimeout = Duration(seconds: 120); // Normal operations
  static const Duration longReceiveTimeout = Duration(minutes: 10); // Heavy operations (mesh, AI)
}
