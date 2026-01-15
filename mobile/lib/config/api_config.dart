/// API Configuration for ReimagineAI
class ApiConfig {
  // Change this to your backend URL based on your platform:
  // - Windows/macOS/Linux desktop: http://localhost:8000
  // - Android emulator: http://10.0.2.2:8000
  // - iOS simulator: http://localhost:8000
  // - Physical device: http://YOUR_COMPUTER_IP:8000
  
  static const String baseUrl = 'http://localhost:8000'; // Windows desktop / Web
  // static const String baseUrl = 'http://10.0.2.2:8000'; // Android emulator
  // static const String baseUrl = 'http://192.168.1.X:8000'; // Physical device
  
  static const String apiVersion = '/api/v1';
  
  // Endpoints
  static const String chat = '$apiVersion/chat/';
  static const String chatWithImage = '$apiVersion/chat/with-image';
  static const String conversations = '$apiVersion/chat/conversations';
  static const String generateImages = '$apiVersion/images/generate';
  static const String analyzeRoom = '$apiVersion/images/analyze';
  static const String redesignRoom = '$apiVersion/images/redesign';
  
  // Timeouts
  static const Duration connectTimeout = Duration(seconds: 30);
  static const Duration receiveTimeout = Duration(seconds: 120); // Image generation can take time
}
