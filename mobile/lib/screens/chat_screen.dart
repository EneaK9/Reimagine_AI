import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:provider/provider.dart';
import 'package:flutter_staggered_animations/flutter_staggered_animations.dart';
import '../providers/chat_provider.dart';
import '../widgets/chat_bubble.dart';
import '../widgets/chat_input.dart';
import '../widgets/conversation_drawer.dart';
import '../widgets/conversation_sidebar.dart';
import '../widgets/landing/decorations.dart';
import '../theme/app_theme.dart';
import 'room_scan_screen.dart';

/// Design studio — mobile uses a compact drawer layout; web uses a
/// desktop shell with a persistent sidebar and a distinct home canvas.
class ChatScreen extends StatefulWidget {
  const ChatScreen({super.key});

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  final ScrollController _scrollController = ScrollController();
  final GlobalKey<ScaffoldState> _scaffoldKey = GlobalKey<ScaffoldState>();
  final GlobalKey<ChatInputState> _chatInputKey = GlobalKey<ChatInputState>();
  int _selectedRoomIndex = 0;

  static const _roomTypes = [
    (Icons.weekend_outlined, 'Living Room'),
    (Icons.bed_outlined, 'Bedroom'),
    (Icons.bathtub_outlined, 'Bathroom'),
    (Icons.countertops_outlined, 'Kitchen'),
    (Icons.dining_outlined, 'Dining'),
    (Icons.door_front_door_outlined, 'Entryway'),
  ];

  static const _prompts = [
    'Make it warmer with oak and linen',
    'Modern minimal with black accents',
    'Bright Scandinavian living room',
    'Luxury hotel suite vibe',
  ];

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<ChatProvider>().startNewConversation();
    });
  }

  @override
  void dispose() {
    _scrollController.dispose();
    super.dispose();
  }

  String get _selectedRoomLabel => _roomTypes[_selectedRoomIndex].$2;

  void _scrollToBottom() {
    if (_scrollController.hasClients) {
      Future.delayed(const Duration(milliseconds: 100), () {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      });
    }
  }

  void _usePrompt(String prompt) {
    _chatInputKey.currentState
        ?.setDraft('Redesign my $_selectedRoomLabel: $prompt');
  }

  @override
  Widget build(BuildContext context) {
    // Web always gets the desktop shell; native mobile keeps the drawer UX.
    if (kIsWeb) {
      return _buildWebShell();
    }
    return _buildMobileShell();
  }

  // ---------------------------------------------------------------------------
  // Mobile shell — drawer + stacked column
  // ---------------------------------------------------------------------------

  Widget _buildMobileShell() {
    return Scaffold(
      key: _scaffoldKey,
      drawer: const ConversationDrawer(),
      backgroundColor: AppTheme.background,
      body: SafeArea(
        child: Column(
          children: [
            _buildMobileAppBar(),
            Expanded(child: _buildChatArea(isWeb: false)),
            _buildInputArea(),
          ],
        ),
      ),
    );
  }

  Widget _buildMobileAppBar() {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        border: Border(bottom: BorderSide(color: AppTheme.gridLine)),
      ),
      child: Row(
        children: [
          _IconBtn(
            icon: Icons.menu_rounded,
            tooltip: 'Menu',
            onTap: () => _scaffoldKey.currentState?.openDrawer(),
          ),
          const SizedBox(width: 12),
          Text(
            '✱',
            style: GoogleFonts.interTight(
              fontSize: 17,
              fontWeight: FontWeight.w700,
              color: AppTheme.ink,
            ),
          ),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              'ReimagineAI',
              style: GoogleFonts.interTight(
                fontSize: 15,
                fontWeight: FontWeight.w700,
                color: AppTheme.ink,
              ),
            ),
          ),
          _IconBtn(
            icon: Icons.add_rounded,
            tooltip: 'New design',
            onTap: () => context.read<ChatProvider>().startNewConversation(),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Web shell — persistent sidebar + desktop canvas
  // ---------------------------------------------------------------------------

  Widget _buildWebShell() {
    return Scaffold(
      backgroundColor: AppTheme.background,
      body: Row(
        children: [
          const SizedBox(
            width: 280,
            child: DecoratedBox(
              decoration: BoxDecoration(
                border: Border(right: BorderSide(color: AppTheme.gridLine)),
              ),
              child: ConversationSidebar(),
            ),
          ),
          Expanded(
            child: Column(
              children: [
                _buildWebTopBar(),
                Expanded(child: _buildChatArea(isWeb: true)),
                _buildInputArea(),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildWebTopBar() {
    return Container(
      height: 64,
      padding: const EdgeInsets.symmetric(horizontal: 28),
      decoration: const BoxDecoration(
        color: AppTheme.surface,
        border: Border(bottom: BorderSide(color: AppTheme.gridLine)),
      ),
      child: Row(
        children: [
          Text(
            'Studio',
            style: GoogleFonts.interTight(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: AppTheme.ink,
            ),
          ),
          const SizedBox(width: 12),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
            decoration: BoxDecoration(
              border: Border.all(color: AppTheme.primaryColor),
            ),
            child: Text(
              'WEB',
              style: GoogleFonts.interTight(
                fontSize: 10,
                fontWeight: FontWeight.w700,
                letterSpacing: 1,
                color: AppTheme.primaryColor,
              ),
            ),
          ),
          const Spacer(),
          Text(
            'Selected · $_selectedRoomLabel',
            style: GoogleFonts.interTight(
              fontSize: 13,
              color: AppTheme.textMuted,
            ),
          ),
          const SizedBox(width: 16),
          TextButton(
            onPressed: () =>
                context.read<ChatProvider>().startNewConversation(),
            style: TextButton.styleFrom(
              foregroundColor: AppTheme.ink,
              overlayColor: Colors.transparent,
            ),
            child: Text(
              'New design',
              style: GoogleFonts.interTight(
                fontSize: 13,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  // ---------------------------------------------------------------------------
  // Shared chat / empty states
  // ---------------------------------------------------------------------------

  Widget _buildChatArea({required bool isWeb}) {
    return Consumer<ChatProvider>(
      builder: (context, provider, child) {
        if (provider.messages.isEmpty) {
          return isWeb ? _buildWebStudioHome() : _buildMobileStudioHome();
        }

        WidgetsBinding.instance.addPostFrameCallback((_) => _scrollToBottom());

        return AnimationLimiter(
          child: ListView.builder(
            controller: _scrollController,
            padding: EdgeInsets.symmetric(
              vertical: 16,
              horizontal: isWeb ? 48 : 8,
            ),
            itemCount: provider.messages.length,
            itemBuilder: (context, index) {
              return AnimationConfiguration.staggeredList(
                position: index,
                duration: const Duration(milliseconds: 280),
                child: SlideAnimation(
                  verticalOffset: 24,
                  child: FadeInAnimation(
                    child: Center(
                      child: ConstrainedBox(
                        constraints: BoxConstraints(
                          maxWidth: isWeb ? 820 : double.infinity,
                        ),
                        child: ChatBubble(message: provider.messages[index]),
                      ),
                    ),
                  ),
                ),
              );
            },
          ),
        );
      },
    );
  }

  /// Mobile empty state — compact vertical stack.
  Widget _buildMobileStudioHome() {
    return SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(16, 20, 16, 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(
            'DESIGN STUDIO',
            style: GoogleFonts.interTight(
              fontSize: 11,
              fontWeight: FontWeight.w700,
              letterSpacing: 1.6,
              color: AppTheme.primaryColor,
            ),
          ),
          const SizedBox(height: 8),
          Text.rich(
            TextSpan(
              style: GoogleFonts.interTight(
                fontSize: 28,
                fontWeight: FontWeight.w700,
                height: 1.15,
                color: AppTheme.ink,
              ),
              children: [
                const TextSpan(text: 'Redesign '),
                TextSpan(
                  text: 'your space',
                  style: GoogleFonts.interTight(
                    fontSize: 28,
                    fontWeight: FontWeight.w600,
                    fontStyle: FontStyle.italic,
                    color: AppTheme.ink,
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            'Upload a photo, scan in 3D, or just chat your vision.',
            style: GoogleFonts.interTight(
              fontSize: 13,
              color: AppTheme.textSecondary,
            ),
          ),
          const SizedBox(height: 18),
          _QuickAction(
            icon: Icons.add_a_photo_outlined,
            title: 'Upload photo',
            subtitle: 'Redesign from an image',
            onTap: () => _chatInputKey.currentState?.showImageSourcePicker(),
          ),
          const SizedBox(height: 8),
          _QuickAction(
            icon: Icons.view_in_ar_outlined,
            title: '3D room scan',
            subtitle: 'Depth mesh from a photo',
            accent: true,
            badge: 'NEW',
            onTap: () {
              Navigator.push(
                context,
                MaterialPageRoute(builder: (_) => const RoomScanScreen()),
              );
            },
          ),
          const SizedBox(height: 18),
          Text(
            'Room type',
            style: GoogleFonts.interTight(
              fontSize: 12,
              fontWeight: FontWeight.w600,
              color: AppTheme.textMuted,
            ),
          ),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (var i = 0; i < _roomTypes.length; i++)
                _RoomChip(
                  icon: _roomTypes[i].$1,
                  label: _roomTypes[i].$2,
                  selected: _selectedRoomIndex == i,
                  onTap: () => setState(() => _selectedRoomIndex = i),
                ),
            ],
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final p in _prompts)
                _PromptChip(label: p, onTap: () => _usePrompt(p)),
            ],
          ),
        ],
      ),
    );
  }

  /// Web empty state — LUXE desktop canvas with hero image + grid.
  Widget _buildWebStudioHome() {
    return Stack(
      children: [
        Positioned.fill(
          child: CustomPaint(
            painter: const GridLinesPainter(
              columnCount: 6,
              rowCount: 4,
              showCrosshairs: true,
            ),
          ),
        ),
        SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(40, 36, 40, 28),
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 1100),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(
                      flex: 5,
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            'AI INTERIOR STUDIO',
                            style: GoogleFonts.interTight(
                              fontSize: 12,
                              fontWeight: FontWeight.w700,
                              letterSpacing: 2,
                              color: AppTheme.primaryColor,
                            ),
                          ),
                          const SizedBox(height: 14),
                          Text.rich(
                            TextSpan(
                              style: GoogleFonts.interTight(
                                fontSize: 48,
                                fontWeight: FontWeight.w700,
                                height: 1.08,
                                letterSpacing: -1,
                                color: AppTheme.ink,
                              ),
                              children: [
                                const TextSpan(text: 'Bring Vision\n'),
                                TextSpan(
                                  text: 'to Life',
                                  style: GoogleFonts.interTight(
                                    fontSize: 48,
                                    fontWeight: FontWeight.w600,
                                    fontStyle: FontStyle.italic,
                                    height: 1.08,
                                    letterSpacing: -1,
                                    color: AppTheme.ink,
                                  ),
                                ),
                                const TextSpan(text: ' with AI'),
                                WidgetSpan(
                                  alignment: PlaceholderAlignment.middle,
                                  child: Container(
                                    margin: const EdgeInsets.only(left: 8),
                                    width: 12,
                                    height: 12,
                                    color: AppTheme.primaryColor,
                                  ),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 16),
                          Text(
                            'Start from a photo, a 3D scan, or a short description.\n'
                            'Get multiple redesign variations in about a minute.',
                            style: GoogleFonts.interTight(
                              fontSize: 15,
                              height: 1.55,
                              color: AppTheme.textSecondary,
                            ),
                          ),
                          const SizedBox(height: 28),
                          Row(
                            children: [
                              Expanded(
                                child: _WebHeroAction(
                                  title: 'Upload photo',
                                  subtitle: 'Best for redesigns',
                                  icon: Icons.add_a_photo_outlined,
                                  onTap: () => _chatInputKey.currentState
                                      ?.showImageSourcePicker(),
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: _WebHeroAction(
                                  title: '3D room scan',
                                  subtitle: 'Photo → depth mesh',
                                  icon: Icons.view_in_ar_outlined,
                                  filled: true,
                                  onTap: () {
                                    Navigator.push(
                                      context,
                                      MaterialPageRoute(
                                        builder: (_) => const RoomScanScreen(),
                                      ),
                                    );
                                  },
                                ),
                              ),
                              const SizedBox(width: 12),
                              Expanded(
                                child: _WebHeroAction(
                                  title: 'Chat design',
                                  subtitle: 'Text-only ideas',
                                  icon: Icons.chat_bubble_outline_rounded,
                                  onTap: () =>
                                      _chatInputKey.currentState?.focusField(),
                                ),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(width: 36),
                    Expanded(
                      flex: 4,
                      child: AspectRatio(
                        aspectRatio: 3 / 4,
                        child: NotchedImage(
                          asset: 'assets/images/landing/hero_main.png',
                          corner: NotchCorner.topLeft,
                          notchSize: 64,
                          semanticLabel: 'Studio inspiration interior',
                        ),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 40),
                Text(
                  'Room focus',
                  style: GoogleFonts.interTight(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textMuted,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (var i = 0; i < _roomTypes.length; i++)
                      _RoomChip(
                        icon: _roomTypes[i].$1,
                        label: _roomTypes[i].$2,
                        selected: _selectedRoomIndex == i,
                        onTap: () => setState(() => _selectedRoomIndex = i),
                      ),
                  ],
                ),
                const SizedBox(height: 28),
                Text(
                  'Prompt starters',
                  style: GoogleFonts.interTight(
                    fontSize: 13,
                    fontWeight: FontWeight.w600,
                    color: AppTheme.textMuted,
                  ),
                ),
                const SizedBox(height: 12),
                Wrap(
                  spacing: 10,
                  runSpacing: 10,
                  children: [
                    for (final p in _prompts)
                      _PromptChip(label: p, onTap: () => _usePrompt(p)),
                  ],
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _buildInputArea() {
    return Consumer<ChatProvider>(
      builder: (context, provider, child) {
        final errorMessage = provider.error;
        if (errorMessage != null) {
          WidgetsBinding.instance.addPostFrameCallback((_) {
            if (!mounted) return;
            ScaffoldMessenger.of(context).showSnackBar(
              SnackBar(
                content: Text(errorMessage),
                backgroundColor: AppTheme.error,
                behavior: SnackBarBehavior.floating,
                action: SnackBarAction(
                  label: 'Dismiss',
                  textColor: Colors.white,
                  onPressed: () => provider.clearError(),
                ),
              ),
            );
            provider.clearError();
          });
        }

        final input = ChatInput(
          key: _chatInputKey,
          onSend: (message) => provider.sendMessage(message),
          onImageSelected: (image) => provider.setSelectedImage(image),
          selectedImage: provider.selectedImage,
          onClearImage: () => provider.clearSelectedImage(),
          isLoading: provider.messages.any((m) => m.isLoading),
          roomHint: _selectedRoomLabel,
        );

        if (!kIsWeb) return input;

        // Web: constrain composer width for a desktop feel
        return ColoredBox(
          color: AppTheme.surface,
          child: Center(
            child: ConstrainedBox(
              constraints: const BoxConstraints(maxWidth: 900),
              child: input,
            ),
          ),
        );
      },
    );
  }
}

// --- shared small widgets ---

class _IconBtn extends StatelessWidget {
  const _IconBtn({
    required this.icon,
    required this.onTap,
    this.tooltip,
  });

  final IconData icon;
  final VoidCallback onTap;
  final String? tooltip;

  @override
  Widget build(BuildContext context) {
    final child = GestureDetector(
      onTap: onTap,
      child: Container(
        width: 34,
        height: 34,
        decoration: BoxDecoration(
          color: AppTheme.background,
          border: Border.all(color: AppTheme.border),
        ),
        child: Icon(icon, size: 18, color: AppTheme.ink),
      ),
    );
    if (tooltip == null) return child;
    return Tooltip(message: tooltip!, child: child);
  }
}

class _QuickAction extends StatefulWidget {
  const _QuickAction({
    required this.icon,
    required this.title,
    required this.subtitle,
    required this.onTap,
    this.accent = false,
    this.badge,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final VoidCallback onTap;
  final bool accent;
  final String? badge;

  @override
  State<_QuickAction> createState() => _QuickActionState();
}

class _QuickActionState extends State<_QuickAction> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final bg = widget.accent
        ? (_hovered ? AppTheme.primaryDark : AppTheme.primaryColor)
        : (_hovered ? AppTheme.panelTone : AppTheme.surface);
    final fg = widget.accent ? Colors.white : AppTheme.ink;
    final sub = widget.accent
        ? Colors.white.withValues(alpha: 0.85)
        : AppTheme.textMuted;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          width: double.infinity,
          padding: const EdgeInsets.all(14),
          decoration: BoxDecoration(
            color: bg,
            border: Border.all(color: widget.accent ? bg : AppTheme.border),
          ),
          child: Row(
            children: [
              Icon(widget.icon, size: 20, color: fg),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text(
                          widget.title,
                          style: GoogleFonts.interTight(
                            fontSize: 14,
                            fontWeight: FontWeight.w700,
                            color: fg,
                          ),
                        ),
                        if (widget.badge != null) ...[
                          const SizedBox(width: 8),
                          Text(
                            widget.badge!,
                            style: GoogleFonts.interTight(
                              fontSize: 9,
                              fontWeight: FontWeight.w700,
                              color: fg,
                            ),
                          ),
                        ],
                      ],
                    ),
                    Text(
                      widget.subtitle,
                      style: GoogleFonts.interTight(fontSize: 11.5, color: sub),
                    ),
                  ],
                ),
              ),
              Icon(Icons.arrow_forward_rounded, size: 16, color: fg),
            ],
          ),
        ),
      ),
    );
  }
}

class _WebHeroAction extends StatefulWidget {
  const _WebHeroAction({
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
    this.filled = false,
  });

  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;
  final bool filled;

  @override
  State<_WebHeroAction> createState() => _WebHeroActionState();
}

class _WebHeroActionState extends State<_WebHeroAction> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    final bg = widget.filled
        ? (_hovered ? AppTheme.primaryDark : AppTheme.primaryColor)
        : (_hovered ? AppTheme.panelTone : AppTheme.surface);
    final fg = widget.filled ? Colors.white : AppTheme.ink;

    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          height: 110,
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: bg,
            border: Border.all(color: widget.filled ? bg : AppTheme.border),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Icon(widget.icon, color: fg, size: 22),
              const Spacer(),
              Text(
                widget.title,
                style: GoogleFonts.interTight(
                  fontSize: 15,
                  fontWeight: FontWeight.w700,
                  color: fg,
                ),
              ),
              Text(
                widget.subtitle,
                style: GoogleFonts.interTight(
                  fontSize: 12,
                  color: widget.filled
                      ? Colors.white.withValues(alpha: 0.85)
                      : AppTheme.textMuted,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _RoomChip extends StatelessWidget {
  const _RoomChip({
    required this.icon,
    required this.label,
    required this.selected,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      child: GestureDetector(
        onTap: onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: selected ? AppTheme.ink : AppTheme.surface,
            border: Border.all(
              color: selected ? AppTheme.ink : AppTheme.border,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                icon,
                size: 15,
                color: selected ? AppTheme.background : AppTheme.textSecondary,
              ),
              const SizedBox(width: 7),
              Text(
                label,
                style: GoogleFonts.interTight(
                  fontSize: 12.5,
                  fontWeight: FontWeight.w600,
                  color: selected ? AppTheme.background : AppTheme.ink,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _PromptChip extends StatefulWidget {
  const _PromptChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  State<_PromptChip> createState() => _PromptChipState();
}

class _PromptChipState extends State<_PromptChip> {
  bool _hovered = false;

  @override
  Widget build(BuildContext context) {
    return MouseRegion(
      cursor: SystemMouseCursors.click,
      onEnter: (_) => setState(() => _hovered = true),
      onExit: (_) => setState(() => _hovered = false),
      child: GestureDetector(
        onTap: widget.onTap,
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 140),
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          decoration: BoxDecoration(
            color: _hovered ? AppTheme.panelTone : Colors.transparent,
            border: Border.all(color: AppTheme.border),
          ),
          child: Text(
            widget.label,
            style: GoogleFonts.interTight(
              fontSize: 12.5,
              fontWeight: FontWeight.w500,
              color: AppTheme.ink,
            ),
          ),
        ),
      ),
    );
  }
}
