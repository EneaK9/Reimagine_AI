import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:cached_network_image/cached_network_image.dart';
import 'package:shimmer/shimmer.dart';
import '../models/message.dart';
import '../theme/app_theme.dart';
import 'image_gallery.dart';

/// Chat message bubble widget - Light theme design
class ChatBubble extends StatelessWidget {
  final Message message;
  
  const ChatBubble({super.key, required this.message});

  bool get isUser => message.role == MessageRole.user;

  /// Get display content - hide [IMAGE_PROMPT] section from AI responses
  String get displayContent {
    String content = message.content;
    
    if (!isUser) {
      final regex = RegExp(r'\[IMAGE_PROMPT\]:?.*', dotAll: true);
      content = content.replaceAll(regex, '').trim();
    }
    
    return content;
  }

  @override
  Widget build(BuildContext context) {
    if (message.isLoading) {
      return _buildLoadingBubble(context);
    }

    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Row(
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (!isUser) _buildAvatar(),
          if (!isUser) const SizedBox(width: 12),
          Flexible(
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                // Show uploaded image above user message
                if (isUser && message.imageUrls.isNotEmpty) ...[
                  _buildUploadedImage(context),
                  const SizedBox(height: 8),
                ],
                _buildMessageBubble(context),
                // Show generated images below AI message
                if (!isUser && message.imageUrls.isNotEmpty) ...[
                  const SizedBox(height: 12),
                  _buildImageGrid(context),
                ],
              ],
            ),
          ),
          if (isUser) const SizedBox(width: 12),
          if (isUser) _buildUserAvatar(),
        ],
      ),
    );
  }

  Widget _buildAvatar() {
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: AppTheme.primaryColor,
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(
            color: AppTheme.primaryColor.withOpacity(0.3),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: const Center(
        child: Icon(
          Icons.home_rounded,
          color: Colors.white,
          size: 20,
        ),
      ),
    );
  }

  Widget _buildUserAvatar() {
    return Container(
      width: 38,
      height: 38,
      decoration: BoxDecoration(
        color: AppTheme.surface,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border),
      ),
      child: const Center(
        child: Icon(
          Icons.person_rounded,
          color: AppTheme.textSecondary,
          size: 20,
        ),
      ),
    );
  }

  Widget _buildMessageBubble(BuildContext context) {
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.72,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
      decoration: BoxDecoration(
        color: isUser ? AppTheme.primaryColor : AppTheme.surface,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(20),
          topRight: const Radius.circular(20),
          bottomLeft: Radius.circular(isUser ? 20 : 6),
          bottomRight: Radius.circular(isUser ? 6 : 20),
        ),
        border: isUser ? null : Border.all(color: AppTheme.border),
        boxShadow: [
          BoxShadow(
            color: isUser 
                ? AppTheme.primaryColor.withOpacity(0.2) 
                : Colors.black.withOpacity(0.04),
            blurRadius: 10,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Text(
        displayContent,
        style: GoogleFonts.dmSans(
          color: isUser ? Colors.white : AppTheme.textPrimary,
          fontSize: 15,
          height: 1.5,
        ),
      ),
    );
  }

  Widget _buildUploadedImage(BuildContext context) {
    final imagePath = message.imageUrls.first;
    
    return Container(
      width: 80,
      height: 80,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        border: Border.all(color: AppTheme.border, width: 2),
        boxShadow: AppTheme.cardShadow,
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(10),
        child: _buildImageFromPath(imagePath),
      ),
    );
  }

  Widget _buildImageFromPath(String imagePath) {
    // Local file path
    if (imagePath.startsWith('/') || imagePath.contains(':\\') || (!imagePath.contains('://') && !imagePath.startsWith('data:'))) {
      final file = File(imagePath);
      if (file.existsSync()) {
        return Image.file(
          file,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => _buildImageError(),
        );
      }
    }
    
    // Base64 data URL
    if (imagePath.startsWith('data:image')) {
      try {
        final base64Data = imagePath.split(',').last;
        final bytes = base64Decode(base64Data);
        return Image.memory(
          bytes,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => _buildImageError(),
        );
      } catch (e) {
        return _buildImageError();
      }
    }
    
    // Network URL
    return CachedNetworkImage(
      imageUrl: imagePath,
      fit: BoxFit.cover,
      placeholder: (context, url) => Shimmer.fromColors(
        baseColor: AppTheme.border,
        highlightColor: AppTheme.surface,
        child: Container(color: AppTheme.border),
      ),
      errorWidget: (context, url, error) => _buildImageError(),
    );
  }

  Widget _buildImageError() {
    return Container(
      color: AppTheme.inputBackground,
      child: const Center(
        child: Icon(
          Icons.broken_image_outlined,
          color: AppTheme.textMuted,
          size: 24,
        ),
      ),
    );
  }

  Widget _buildImageGrid(BuildContext context) {
    final images = message.imageUrls;
    
    // Single image - show as medium sized preview
    if (images.length == 1) {
      return GestureDetector(
        onTap: () => _openImageGallery(context, 0),
        child: Container(
          constraints: const BoxConstraints(
            maxWidth: 300,
            maxHeight: 240,
          ),
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(16),
            border: Border.all(color: AppTheme.border),
            boxShadow: AppTheme.cardShadow,
          ),
          child: ClipRRect(
            borderRadius: BorderRadius.circular(15),
            child: Hero(
              tag: 'image_${message.id}_0',
              child: _buildImage(images[0]),
            ),
          ),
        ),
      );
    }
    
    // Multiple images - show as grid
    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.65,
      ),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: AppTheme.border),
      ),
      child: ClipRRect(
        borderRadius: BorderRadius.circular(15),
        child: GridView.builder(
          shrinkWrap: true,
          physics: const NeverScrollableScrollPhysics(),
          gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
            crossAxisCount: 2,
            crossAxisSpacing: 2,
            mainAxisSpacing: 2,
          ),
          itemCount: images.length,
          itemBuilder: (context, index) {
            return GestureDetector(
              onTap: () => _openImageGallery(context, index),
              child: Hero(
                tag: 'image_${message.id}_$index',
                child: _buildImage(images[index]),
              ),
            );
          },
        ),
      ),
    );
  }

  Widget _buildImage(String imageSource) {
    if (imageSource.startsWith('data:image')) {
      try {
        final base64Data = imageSource.split(',').last;
        final bytes = base64Decode(base64Data);
        
        return Image.memory(
          bytes,
          fit: BoxFit.cover,
          errorBuilder: (context, error, stackTrace) => _buildImageError(),
        );
      } catch (e) {
        return _buildImageError();
      }
    }
    
    return CachedNetworkImage(
      imageUrl: imageSource,
      fit: BoxFit.cover,
      placeholder: (context, url) => Shimmer.fromColors(
        baseColor: AppTheme.border,
        highlightColor: AppTheme.surface,
        child: Container(color: AppTheme.border),
      ),
      errorWidget: (context, url, error) => _buildImageError(),
    );
  }

  void _openImageGallery(BuildContext context, int initialIndex) {
    Navigator.push(
      context,
      MaterialPageRoute(
        builder: (context) => ImageGalleryScreen(
          imageUrls: message.imageUrls,
          initialIndex: initialIndex,
        ),
      ),
    );
  }

  Widget _buildLoadingBubble(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _buildAvatar(),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
            decoration: BoxDecoration(
              color: AppTheme.surface,
              borderRadius: const BorderRadius.only(
                topLeft: Radius.circular(20),
                topRight: Radius.circular(20),
                bottomLeft: Radius.circular(6),
                bottomRight: Radius.circular(20),
              ),
              border: Border.all(color: AppTheme.border),
            ),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                _buildDot(0),
                const SizedBox(width: 6),
                _buildDot(1),
                const SizedBox(width: 6),
                _buildDot(2),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildDot(int index) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0, end: 1),
      duration: Duration(milliseconds: 600 + (index * 200)),
      builder: (context, value, child) {
        return AnimatedContainer(
          duration: const Duration(milliseconds: 300),
          width: 8,
          height: 8,
          decoration: BoxDecoration(
            color: AppTheme.primaryColor.withOpacity(0.3 + (0.7 * value)),
            shape: BoxShape.circle,
          ),
        );
      },
    );
  }
}
