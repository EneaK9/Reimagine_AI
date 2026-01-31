import 'dart:io';
import 'package:flutter/foundation.dart';
import '../models/message.dart';
import '../models/conversation.dart';
import '../services/api_service.dart';

/// Chat state management
class ChatProvider with ChangeNotifier {
  final ApiService _apiService = ApiService();
  
  Conversation? _currentConversation;
  List<ConversationSummary> _conversations = [];
  bool _isLoading = false;
  String? _error;
  File? _selectedImage;

  // Getters
  Conversation? get currentConversation => _currentConversation;
  List<Message> get messages => _currentConversation?.messages ?? [];
  List<ConversationSummary> get conversations => _conversations;
  bool get isLoading => _isLoading;
  String? get error => _error;
  File? get selectedImage => _selectedImage;
  bool get hasSelectedImage => _selectedImage != null;

  /// Start a new conversation
  void startNewConversation() {
    _currentConversation = Conversation.create();
    _error = null;
    notifyListeners();
  }

  /// Set selected image for upload
  void setSelectedImage(File? image) {
    _selectedImage = image;
    notifyListeners();
  }

  /// Clear selected image
  void clearSelectedImage() {
    _selectedImage = null;
    notifyListeners();
  }

  /// Send a message
  Future<void> sendMessage(String content) async {
    if (content.trim().isEmpty && _selectedImage == null) return;

    _error = null;
    
    // Create conversation if needed
    _currentConversation ??= Conversation.create();

    // Add user message
    final userMessage = Message.user(
      content,
      imageUrl: _selectedImage?.path,
    );
    _currentConversation = _currentConversation!.addMessage(userMessage);
    
    // Add loading indicator
    _currentConversation = _currentConversation!.addMessage(Message.loading());
    notifyListeners();

    try {
      ChatResponse response;
      
      if (_selectedImage != null) {
        // Send with image
        response = await _apiService.sendMessageWithImage(
          message: content,
          imageFile: _selectedImage!,
          conversationId: _currentConversation!.id,
        );
        _selectedImage = null; // Clear after sending
      } else {
        // Send text only
        response = await _apiService.sendMessage(
          message: content,
          conversationId: _currentConversation!.id,
        );
      }

      // Remove loading message
      final messagesWithoutLoading = _currentConversation!.messages
          .where((m) => !m.isLoading)
          .toList();

      // Add assistant response
      final assistantMessage = Message.assistant(
        response.message,
        imageUrls: response.generatedImages,
      );

      _currentConversation = _currentConversation!.copyWith(
        id: response.conversationId,
        messages: [...messagesWithoutLoading, assistantMessage],
      );

    } catch (e) {
      // Remove loading message on error
      final messagesWithoutLoading = _currentConversation!.messages
          .where((m) => !m.isLoading)
          .toList();
      
      _currentConversation = _currentConversation!.copyWith(
        messages: messagesWithoutLoading,
      );
      
      _error = e.toString();
    }

    notifyListeners();
  }

  /// Load conversation history
  Future<void> loadConversations() async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      _conversations = await _apiService.getConversations();
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Load a specific conversation
  Future<void> loadConversation(String conversationId) async {
    _isLoading = true;
    _error = null;
    notifyListeners();

    try {
      final data = await _apiService.getConversation(conversationId);
      _currentConversation = Conversation.fromJson(data);
    } catch (e) {
      _error = e.toString();
    }

    _isLoading = false;
    notifyListeners();
  }

  /// Delete a conversation
  Future<void> deleteConversation(String conversationId) async {
    try {
      await _apiService.deleteConversation(conversationId);
      
      // Remove from local list
      _conversations.removeWhere((c) => c.id == conversationId);
      
      // If deleted conversation was current, clear it
      if (_currentConversation?.id == conversationId) {
        _currentConversation = null;
      }
      
      notifyListeners();
    } catch (e) {
      _error = e.toString();
      notifyListeners();
    }
  }

  /// Check backend health
  Future<bool> checkHealth() async {
    return await _apiService.healthCheck();
  }

  /// Clear error
  void clearError() {
    _error = null;
    notifyListeners();
  }
}
