/// API Configuration for ReimagineAI
class ApiConfig {
  // Change this to your backend URL based on your platform:
  // - Windows/macOS/Linux desktop: http://localhost:8000
  // - Android emulator: http://10.0.2.2:8000
  // - iOS simulator: http://localhost:8000
  // - Physical device: http://YOUR_COMPUTER_IP:8000
  
  // static const String baseUrl = 'http://localhost:8000'; // Windows desktop / Web
  // static const String baseUrl = 'http://10.0.2.2:8000'; // Android emulator
  static const String baseUrl = 'http://192.168.0.92:8000'; // Physical device (your computer's IP)
  
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
  
  // Room/3D Scanning Endpoints
  static const String rooms = '$apiVersion/rooms';
  static const String roomUpload = '$apiVersion/rooms/upload';
  static String roomById(String id) => '$apiVersion/rooms/$id';
  static String roomEdit(String id) => '$apiVersion/rooms/$id/edit';
  static String roomGenerateTexture(String id) => '$apiVersion/rooms/$id/generate-texture';
  
  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 120); // Image generation can take time
}
