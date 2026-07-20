import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:intl/intl.dart';
import '../providers/chat_provider.dart';
import '../providers/auth_provider.dart';
import '../services/api_service.dart';
import '../screens/login_screen.dart';
import '../theme/app_theme.dart';

/// Conversation history panel — used as a Drawer on mobile and a fixed
/// sidebar on web.
class ConversationSidebar extends StatefulWidget {
  const ConversationSidebar({
    super.key,
    this.asDrawer = false,
    this.onClose,
  });

  /// When true, wraps content for use inside a [Drawer].
  final bool asDrawer;

  /// Optional close callback (e.g. pop drawer on mobile after selection).
  final VoidCallback? onClose;

  @override
  State<ConversationSidebar> createState() => _ConversationSidebarState();
}

class _ConversationSidebarState extends State<ConversationSidebar> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ChatProvider>().loadConversations();
    });
  }

  void _closeIfNeeded() => widget.onClose?.call();

  @override
  Widget build(BuildContext context) {
    final body = ColoredBox(
      color: AppTheme.surface,
      child: Column(
        children: [
          _buildHeader(),
          const Divider(height: 1, color: AppTheme.gridLine),
          _buildNewChatButton(),
          const Divider(height: 1, color: AppTheme.gridLine),
          Expanded(child: _buildConversationList()),
          const Divider(height: 1, color: AppTheme.gridLine),
          _buildFooter(),
        ],
      ),
    );

    if (widget.asDrawer) {
      return Drawer(
        backgroundColor: AppTheme.surface,
        shape: const RoundedRectangleBorder(),
        child: SafeArea(child: body),
      );
    }

    return body;
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.fromLTRB(18, 18, 18, 16),
      child: Row(
        children: [
          Text(
            '✱',
            style: GoogleFonts.interTight(
              fontSize: 20,
              fontWeight: FontWeight.w700,
              color: AppTheme.ink,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  'ReimagineAI',
                  style: GoogleFonts.interTight(
                    color: AppTheme.ink,
                    fontSize: 16,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                Text(
                  'Design history',
                  style: GoogleFonts.interTight(
                    color: AppTheme.textMuted,
                    fontSize: 12,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildNewChatButton() {
    return Padding(
      padding: const EdgeInsets.all(14),
      child: SizedBox(
        width: double.infinity,
        height: 42,
        child: ElevatedButton(
          onPressed: () {
            context.read<ChatProvider>().startNewConversation();
            _closeIfNeeded();
          },
          style: ElevatedButton.styleFrom(
            backgroundColor: AppTheme.ink,
            foregroundColor: AppTheme.background,
            elevation: 0,
            shape: const RoundedRectangleBorder(),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              const Icon(Icons.add_rounded, size: 18),
              const SizedBox(width: 8),
              Text(
                'New design',
                style: GoogleFonts.interTight(
                  fontSize: 13.5,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildConversationList() {
    return Consumer<ChatProvider>(
      builder: (context, provider, child) {
        if (provider.isLoading) {
          return const Center(
            child: CircularProgressIndicator(
              color: AppTheme.primaryColor,
              strokeWidth: 2,
            ),
          );
        }

        if (provider.conversations.isEmpty) {
          return Center(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(
                    'No designs yet',
                    style: GoogleFonts.interTight(
                      color: AppTheme.ink,
                      fontSize: 15,
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Start a new design to see it here.',
                    textAlign: TextAlign.center,
                    style: GoogleFonts.interTight(
                      color: AppTheme.textMuted,
                      fontSize: 13,
                    ),
                  ),
                ],
              ),
            ),
          );
        }

        return ListView.builder(
          padding: const EdgeInsets.symmetric(vertical: 6),
          itemCount: provider.conversations.length,
          itemBuilder: (context, index) {
            final conv = provider.conversations[index];
            final isSelected = provider.currentConversation?.id == conv.id;
            return _buildConversationTile(conv, isSelected);
          },
        );
      },
    );
  }

  void _showDeleteDialog(String convId, String title) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        backgroundColor: AppTheme.surface,
        shape: const RoundedRectangleBorder(),
        title: Text(
          'Delete conversation',
          style: GoogleFonts.interTight(
            color: AppTheme.ink,
            fontWeight: FontWeight.w700,
          ),
        ),
        content: Text(
          'Delete "$title"? This cannot be undone.',
          style: GoogleFonts.interTight(color: AppTheme.textSecondary),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            style: TextButton.styleFrom(overlayColor: Colors.transparent),
            child: Text(
              'Cancel',
              style: GoogleFonts.interTight(color: AppTheme.textMuted),
            ),
          ),
          TextButton(
            onPressed: () {
              context.read<ChatProvider>().deleteConversation(convId);
              Navigator.pop(context);
            },
            style: TextButton.styleFrom(overlayColor: Colors.transparent),
            child: Text(
              'Delete',
              style: GoogleFonts.interTight(
                color: AppTheme.error,
                fontWeight: FontWeight.w700,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConversationTile(ConversationSummary conv, bool isSelected) {
    final dateFormat = DateFormat('MMM d · h:mm a');

    return GestureDetector(
      onTap: () {
        context.read<ChatProvider>().loadConversation(conv.id);
        _closeIfNeeded();
      },
      child: Container(
        margin: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
        padding: const EdgeInsets.fromLTRB(12, 10, 8, 10),
        decoration: BoxDecoration(
          color: isSelected ? AppTheme.panelTone : Colors.transparent,
          border: Border.all(
            color: isSelected ? AppTheme.gridLine : Colors.transparent,
          ),
        ),
        child: Row(
          children: [
            Icon(
              conv.imageCount > 0
                  ? Icons.image_outlined
                  : Icons.chat_bubble_outline_rounded,
              size: 16,
              color: isSelected ? AppTheme.primaryColor : AppTheme.textMuted,
            ),
            const SizedBox(width: 10),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    conv.title,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: GoogleFonts.interTight(
                      color: AppTheme.ink,
                      fontSize: 13,
                      fontWeight:
                          isSelected ? FontWeight.w700 : FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    dateFormat.format(conv.updatedAt),
                    style: GoogleFonts.interTight(
                      color: AppTheme.textMuted,
                      fontSize: 11,
                    ),
                  ),
                ],
              ),
            ),
            IconButton(
              onPressed: () => _showDeleteDialog(conv.id, conv.title),
              icon: const Icon(Icons.delete_outline_rounded, size: 16),
              color: AppTheme.textMuted,
              visualDensity: VisualDensity.compact,
              tooltip: 'Delete',
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFooter() {
    return Consumer<AuthProvider>(
      builder: (context, auth, child) {
        return Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            children: [
              if (auth.isLoggedIn) ...[
                Container(
                  padding: const EdgeInsets.all(12),
                  decoration: BoxDecoration(
                    border: Border.all(color: AppTheme.border),
                  ),
                  child: Row(
                    children: [
                      Container(
                        width: 34,
                        height: 34,
                        color: AppTheme.ink,
                        alignment: Alignment.center,
                        child: Text(
                          auth.user!.username[0].toUpperCase(),
                          style: GoogleFonts.interTight(
                            color: AppTheme.background,
                            fontWeight: FontWeight.w700,
                            fontSize: 14,
                          ),
                        ),
                      ),
                      const SizedBox(width: 10),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(
                              auth.user!.username,
                              style: GoogleFonts.interTight(
                                color: AppTheme.ink,
                                fontWeight: FontWeight.w600,
                                fontSize: 13,
                              ),
                            ),
                            Text(
                              auth.user!.email,
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                              style: GoogleFonts.interTight(
                                color: AppTheme.textMuted,
                                fontSize: 11,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 10),
              ],
              Row(
                children: [
                  Expanded(
                    child: _FooterBtn(
                      icon: Icons.settings_outlined,
                      label: 'Settings',
                      onTap: () {
                        ScaffoldMessenger.of(context).showSnackBar(
                          const SnackBar(
                            content: Text('Settings coming soon'),
                            backgroundColor: AppTheme.ink,
                            behavior: SnackBarBehavior.floating,
                          ),
                        );
                      },
                    ),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: _FooterBtn(
                      icon: auth.isLoggedIn
                          ? Icons.logout_rounded
                          : Icons.login_rounded,
                      label: auth.isLoggedIn ? 'Logout' : 'Login',
                      destructive: auth.isLoggedIn,
                      onTap: () {
                        if (auth.isLoggedIn) auth.logout();
                        _closeIfNeeded();
                        Navigator.pushReplacement(
                          context,
                          MaterialPageRoute(
                            builder: (_) => const LoginScreen(),
                          ),
                        );
                      },
                    ),
                  ),
                ],
              ),
            ],
          ),
        );
      },
    );
  }
}

class _FooterBtn extends StatelessWidget {
  const _FooterBtn({
    required this.icon,
    required this.label,
    required this.onTap,
    this.destructive = false,
  });

  final IconData icon;
  final String label;
  final VoidCallback onTap;
  final bool destructive;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(vertical: 10),
        decoration: BoxDecoration(
          border: Border.all(
            color: destructive
                ? AppTheme.error.withValues(alpha: 0.35)
                : AppTheme.border,
          ),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              icon,
              size: 15,
              color: destructive ? AppTheme.error : AppTheme.textSecondary,
            ),
            const SizedBox(width: 6),
            Text(
              label,
              style: GoogleFonts.interTight(
                color: destructive ? AppTheme.error : AppTheme.textSecondary,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
