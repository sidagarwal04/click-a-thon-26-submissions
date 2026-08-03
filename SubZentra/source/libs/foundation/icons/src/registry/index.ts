/**
 * Icon Registry Initialization
 *
 * Registers all available icons from lucide-react.
 * lucide-react is tree-shakeable -- only the icons explicitly imported
 * here end up in the bundle. Icons are organized by category.
 */

import {
  // Status
  AlertCircle,
  AlertTriangle,
  Archive,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ArrowUp,
  Bell,
  BellOff,
  Bookmark,
  Box,
  Calendar,
  Camera,
  Check,
  CheckCircle,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Clipboard,
  ClipboardCopy,
  Clock,
  Cog,
  Columns,
  Compass,
  Copy,
  CreditCard,
  Database,
  Download,
  Edit,
  Edit2,
  Edit3,
  ExternalLink,
  Eye,
  EyeOff,
  File,
  FileText,
  Filter,
  Folder,
  FolderOpen,
  Grid,
  Heart,
  HelpCircle,
  // Navigation
  Home,
  Image,
  Inbox,
  Info,
  Key,
  Layout,
  Link,
  List,
  Loader2,
  Lock,
  LogIn,
  LogOut,
  Mail,
  Maximize,
  Menu,
  MessageSquare,
  Minimize,
  Minus,
  MoreHorizontal,
  MoreVertical,
  Navigation,
  Navigation2,
  Network,
  Package,
  PanelLeft,
  Phone,
  Plus,
  // Additional common
  RefreshCw,
  RotateCcw,
  RotateCw,
  Rows,
  Save,
  Scissors,
  // Actions
  Search,
  Send,
  Settings,
  Share,
  Share2,
  Shield,
  ShoppingCart,
  Sidebar,
  SortAsc,
  SortDesc,
  Sparkles,
  Star,
  Tag,
  Tags,
  ThumbsDown,
  ThumbsUp,
  Trash,
  Trash2,
  Unlock,
  Upload,
  // UI
  User,
  UserMinus,
  UserPlus,
  Users,
  Video,
  Wrench,
  X,
  XCircle,
  ZoomIn,
  ZoomOut,
} from 'lucide-react';

import { ICON_NAMES, registerIcon } from './registry';

/**
 * Register all icons. Called once at module load.
 */
function initializeIcons(): void {
  // Navigation
  registerIcon({ name: ICON_NAMES.HOME, component: Home });
  registerIcon({ name: ICON_NAMES.MENU, component: Menu });
  registerIcon({ name: ICON_NAMES.CHEVRON_LEFT, component: ChevronLeft });
  registerIcon({ name: ICON_NAMES.CHEVRON_RIGHT, component: ChevronRight });
  registerIcon({ name: ICON_NAMES.CHEVRON_UP, component: ChevronUp });
  registerIcon({ name: ICON_NAMES.CHEVRON_DOWN, component: ChevronDown });
  registerIcon({ name: ICON_NAMES.ARROW_LEFT, component: ArrowLeft });
  registerIcon({ name: ICON_NAMES.ARROW_RIGHT, component: ArrowRight });
  registerIcon({ name: ICON_NAMES.ARROW_UP, component: ArrowUp });
  registerIcon({ name: ICON_NAMES.ARROW_DOWN, component: ArrowDown });
  registerIcon({ name: ICON_NAMES.NAVIGATION, component: Navigation });
  registerIcon({ name: ICON_NAMES.NAVIGATION_2, component: Navigation2 });
  registerIcon({ name: ICON_NAMES.COMPASS, component: Compass });

  // Actions
  registerIcon({ name: ICON_NAMES.SEARCH, component: Search });
  registerIcon({ name: ICON_NAMES.PLUS, component: Plus });
  registerIcon({ name: ICON_NAMES.MINUS, component: Minus });
  registerIcon({ name: ICON_NAMES.EDIT, component: Edit });
  registerIcon({ name: ICON_NAMES.EDIT_2, component: Edit2 });
  registerIcon({ name: ICON_NAMES.EDIT_3, component: Edit3 });
  registerIcon({ name: ICON_NAMES.TRASH, component: Trash });
  registerIcon({ name: ICON_NAMES.TRASH_2, component: Trash2 });
  registerIcon({ name: ICON_NAMES.SAVE, component: Save });
  registerIcon({ name: ICON_NAMES.X, component: X });
  registerIcon({ name: ICON_NAMES.CHECK, component: Check });
  registerIcon({ name: ICON_NAMES.COPY, component: Copy });
  registerIcon({ name: ICON_NAMES.SCISSORS, component: Scissors });
  registerIcon({ name: ICON_NAMES.CLIPBOARD, component: Clipboard });
  registerIcon({ name: ICON_NAMES.CLIPBOARD_COPY, component: ClipboardCopy });
  registerIcon({ name: ICON_NAMES.DOWNLOAD, component: Download });
  registerIcon({ name: ICON_NAMES.UPLOAD, component: Upload });
  registerIcon({ name: ICON_NAMES.SHARE, component: Share });
  registerIcon({ name: ICON_NAMES.SHARE_2, component: Share2 });
  registerIcon({ name: ICON_NAMES.SEND, component: Send });
  registerIcon({ name: ICON_NAMES.MAIL, component: Mail });
  registerIcon({ name: ICON_NAMES.MESSAGE_SQUARE, component: MessageSquare });
  registerIcon({ name: ICON_NAMES.PHONE, component: Phone });
  registerIcon({ name: ICON_NAMES.VIDEO, component: Video });
  registerIcon({ name: ICON_NAMES.CAMERA, component: Camera });
  registerIcon({ name: ICON_NAMES.IMAGE, component: Image });
  registerIcon({ name: ICON_NAMES.FILE, component: File });
  registerIcon({ name: ICON_NAMES.FILE_TEXT, component: FileText });
  registerIcon({ name: ICON_NAMES.FOLDER, component: Folder });
  registerIcon({ name: ICON_NAMES.FOLDER_OPEN, component: FolderOpen });
  registerIcon({ name: ICON_NAMES.SETTINGS, component: Settings });
  registerIcon({ name: ICON_NAMES.MORE_VERTICAL, component: MoreVertical });
  registerIcon({ name: ICON_NAMES.MORE_HORIZONTAL, component: MoreHorizontal });
  registerIcon({ name: ICON_NAMES.FILTER, component: Filter });
  registerIcon({ name: ICON_NAMES.SORT_ASC, component: SortAsc });
  registerIcon({ name: ICON_NAMES.SORT_DESC, component: SortDesc });

  // Status
  registerIcon({ name: ICON_NAMES.ALERT_CIRCLE, component: AlertCircle });
  registerIcon({ name: ICON_NAMES.ALERT_TRIANGLE, component: AlertTriangle });
  registerIcon({ name: ICON_NAMES.INFO, component: Info });
  registerIcon({ name: ICON_NAMES.CHECK_CIRCLE, component: CheckCircle });
  registerIcon({ name: ICON_NAMES.X_CIRCLE, component: XCircle });
  registerIcon({ name: ICON_NAMES.HELP_CIRCLE, component: HelpCircle });
  registerIcon({ name: ICON_NAMES.LOADER_2, component: Loader2 });
  registerIcon({ name: ICON_NAMES.CLOCK, component: Clock });
  registerIcon({ name: ICON_NAMES.CALENDAR, component: Calendar });
  registerIcon({ name: ICON_NAMES.BELL, component: Bell });
  registerIcon({ name: ICON_NAMES.BELL_OFF, component: BellOff });
  registerIcon({ name: ICON_NAMES.STAR, component: Star });
  registerIcon({ name: ICON_NAMES.HEART, component: Heart });
  registerIcon({ name: ICON_NAMES.THUMBS_UP, component: ThumbsUp });
  registerIcon({ name: ICON_NAMES.THUMBS_DOWN, component: ThumbsDown });

  // UI
  registerIcon({ name: ICON_NAMES.USER, component: User });
  registerIcon({ name: ICON_NAMES.USERS, component: Users });
  registerIcon({ name: ICON_NAMES.USER_PLUS, component: UserPlus });
  registerIcon({ name: ICON_NAMES.USER_MINUS, component: UserMinus });
  registerIcon({ name: ICON_NAMES.LOCK, component: Lock });
  registerIcon({ name: ICON_NAMES.UNLOCK, component: Unlock });
  registerIcon({ name: ICON_NAMES.EYE, component: Eye });
  registerIcon({ name: ICON_NAMES.EYE_OFF, component: EyeOff });
  registerIcon({ name: ICON_NAMES.SHIELD, component: Shield });
  registerIcon({ name: ICON_NAMES.KEY, component: Key });
  registerIcon({ name: ICON_NAMES.LOG_IN, component: LogIn });
  registerIcon({ name: ICON_NAMES.LOG_OUT, component: LogOut });
  registerIcon({ name: ICON_NAMES.COG, component: Cog });
  registerIcon({ name: ICON_NAMES.WRENCH, component: Wrench });
  registerIcon({ name: ICON_NAMES.GRID, component: Grid });
  registerIcon({ name: ICON_NAMES.LIST, component: List });
  registerIcon({ name: ICON_NAMES.LAYOUT, component: Layout });
  registerIcon({ name: ICON_NAMES.SIDEBAR, component: Sidebar });
  registerIcon({ name: ICON_NAMES.PANEL_LEFT, component: PanelLeft });
  registerIcon({ name: ICON_NAMES.COLUMNS, component: Columns });
  registerIcon({ name: ICON_NAMES.ROWS, component: Rows });

  // Additional
  registerIcon({ name: ICON_NAMES.REFRESH_CW, component: RefreshCw });
  registerIcon({ name: ICON_NAMES.ROTATE_CW, component: RotateCw });
  registerIcon({ name: ICON_NAMES.ROTATE_CCW, component: RotateCcw });
  registerIcon({ name: ICON_NAMES.ZOOM_IN, component: ZoomIn });
  registerIcon({ name: ICON_NAMES.ZOOM_OUT, component: ZoomOut });
  registerIcon({ name: ICON_NAMES.MAXIMIZE, component: Maximize });
  registerIcon({ name: ICON_NAMES.MINIMIZE, component: Minimize });
  registerIcon({ name: ICON_NAMES.EXTERNAL_LINK, component: ExternalLink });
  registerIcon({ name: ICON_NAMES.LINK, component: Link });
  registerIcon({ name: ICON_NAMES.BOOKMARK, component: Bookmark });
  registerIcon({ name: ICON_NAMES.TAG, component: Tag });
  registerIcon({ name: ICON_NAMES.TAGS, component: Tags });
  registerIcon({ name: ICON_NAMES.SHOPPING_CART, component: ShoppingCart });
  registerIcon({ name: ICON_NAMES.CREDIT_CARD, component: CreditCard });
  registerIcon({ name: ICON_NAMES.PACKAGE, component: Package });
  registerIcon({ name: ICON_NAMES.BOX, component: Box });
  registerIcon({ name: ICON_NAMES.ARCHIVE, component: Archive });
  registerIcon({ name: ICON_NAMES.INBOX, component: Inbox });

  // Data
  registerIcon({ name: ICON_NAMES.DATABASE, component: Database });
  registerIcon({ name: ICON_NAMES.NETWORK, component: Network });
  registerIcon({ name: ICON_NAMES.SPARKLES, component: Sparkles });
}
initializeIcons();
