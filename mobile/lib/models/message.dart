/// Message model for chat
class Message {
  final String id;
  final String content;
  final MessageRole role;
  final List<String> imageUrls;
  final DateTime timestamp;
  final bool isLoading;

  Message({
    required this.id,
    required this.content,
    required this.role,
    this.imageUrls = const [],
    DateTime? timestamp,
    this.isLoading = false,
  }) : timestamp = timestamp ?? DateTime.now();

  factory Message.user(String content, {String? imageUrl}) {
    return Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: content,
      role: MessageRole.user,
      imageUrls: imageUrl != null ? [imageUrl] : [],
    );
  }

  factory Message.assistant(String content, {List<String> imageUrls = const []}) {
    return Message(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      content: content,
      role: MessageRole.assistant,
      imageUrls: imageUrls,
    );
  }

  factory Message.loading() {
    return Message(
      id: 'loading',
      content: '',
      role: MessageRole.assistant,
      isLoading: true,
    );
  }

  factory Message.fromJson(Map<String, dynamic> json) {
    return Message(
      id: json['id'] ?? DateTime.now().millisecondsSinceEpoch.toString(),
      content: json['content'] ?? '',
      role: MessageRole.values.firstWhere(
        (e) => e.name == json['role'],
        orElse: () => MessageRole.assistant,
      ),
      imageUrls: List<String>.from(json['image_urls'] ?? []),
      timestamp: json['timestamp'] != null 
        ? DateTime.parse(json['timestamp']) 
        : DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'content': content,
      'role': role.name,
      'image_urls': imageUrls,
      'timestamp': timestamp.toIso8601String(),
    };
  }

  Message copyWith({
    String? id,
    String? content,
    MessageRole? role,
    List<String>? imageUrls,
    DateTime? timestamp,
    bool? isLoading,
  }) {
    return Message(
      id: id ?? this.id,
      content: content ?? this.content,
      role: role ?? this.role,
      imageUrls: imageUrls ?? this.imageUrls,
      timestamp: timestamp ?? this.timestamp,
      isLoading: isLoading ?? this.isLoading,
    );
  }
}

enum MessageRole { user, assistant, system }
