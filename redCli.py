import curses
import praw
import getpass
import textwrap
import time
from datetime import datetime
import webbrowser
import threading # Still here for future potential
import queue     # Still here for future potential
import os
import configparser # For reading config file
import sys # For exit

# --- Default Configuration (Used if config file is missing/incomplete) ---
DEFAULT_TARGET_SUBREDDITS = ["commandline", "linux", "python", "devops", "selfhosted"]
DEFAULT_POST_LIMIT = 30
DEFAULT_COMMENT_LIMIT = 50
DEFAULT_USER_AGENT = "CursesRedditClient/0.3 by Anonymous User (Please set in config.ini)"

# --- Constants ---
CONFIG_FILE = "config.ini"
LEFT_PANE_WIDTH_RATIO = 0.30
MIN_LEFT_PANE_WIDTH = 20
STATUS_BAR_HEIGHT = 1

# Views
VIEW_LIST = 0
VIEW_POST = 1
VIEW_COMMENTS = 2

# Panes (for VIEW_LIST)
PANE_SUBS = 0
PANE_POSTS = 1

# Colors (adjust as desired)
# ... (Keep existing color definitions) ...
COLOR_HIGHLIGHT_BG = curses.COLOR_BLUE
COLOR_HIGHLIGHT_FG = curses.COLOR_WHITE
COLOR_STATUS_BG = curses.COLOR_BLUE
COLOR_STATUS_FG = curses.COLOR_WHITE
COLOR_TITLE_FG = curses.COLOR_YELLOW
COLOR_META_FG = curses.COLOR_CYAN
COLOR_BORDER_ACTIVE_FG = curses.COLOR_WHITE
COLOR_BORDER_INACTIVE_FG = curses.COLOR_BLUE
COLOR_LINK_FG = curses.COLOR_GREEN
COLOR_TEXTPOST_FG = curses.COLOR_WHITE
COLOR_STICKY_FG = curses.COLOR_MAGENTA # New color for sticky indicator
COLOR_LOADING_FG = curses.COLOR_YELLOW
COLOR_ERROR_FG = curses.COLOR_RED
COLOR_COMMENT_FG = curses.COLOR_WHITE
COLOR_COMMENT_META_FG = curses.COLOR_YELLOW
COLOR_COMMENT_DEPTH_FG = [curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_MAGENTA, curses.COLOR_BLUE]

# --- Helper Functions ---
# ... (keep format_timestamp and safe_addstr) ...
def format_timestamp(timestamp_utc):
    # ... (same as before) ...
    now = datetime.utcnow()
    dt_object = datetime.utcfromtimestamp(timestamp_utc)
    delta = now - dt_object
    seconds = delta.total_seconds()

    if seconds < 60: return f"{int(seconds)}s ago"
    if seconds < 3600: return f"{int(seconds / 60)}m ago"
    if seconds < 86400: return f"{int(seconds / 3600)}h ago"
    return f"{int(seconds / 86400)}d ago"

def safe_addstr(window, y, x, text, attr=0):
    # ... (same as before) ...
    try:
        h, w = window.getmaxyx()
        if y >= h or x >= w or y < 0 or x < 0: return
        available_width = w - x
        if available_width <= 0: return
        truncated_text = text.replace('\n', ' ').replace('\r', '')[:available_width]
        window.addstr(y, x, truncated_text, attr)
    except curses.error:
        pass
    except Exception:
        pass

def draw_loading_pane(window, message="Loading..."):
    """Clears window and displays a centered loading message."""
    h, w = window.getmaxyx()
    window.erase()
    window.border() # Keep the border
    safe_addstr(window, h // 2, (w - len(message)) // 2, message, curses.A_BOLD | curses.color_pair(3)) # Yellow Bold
    try:
        window.refresh()
    except curses.error: pass


# --- Main Application Class ---
class RedditCursesApp:
    def __init__(self, stdscr):
        # ... (keep most __init__ variables) ...
        self.stdscr = stdscr
        self.reddit = None
        self.current_view = VIEW_LIST
        self.active_pane = PANE_SUBS

        # Data storage
        self.posts = {}
        self.comments = {}
        self.current_sub_index = 0
        self.current_post_index = 0
        self.current_comment_index = 0 # Now tracks the actual comment object index
        self.sub_scroll_top = 0
        self.post_scroll_top = 0
        self.post_content_scroll_top = 0
        self.comment_scroll_top = 0 # Tracks the top *visible line* in the flattened list

        self.status_message = "Initializing..."
        self.temp_status_message = None
        self.temp_status_timer = 0
        self.last_fetch_time = {}

        # Configurable values
        self.target_subreddits = DEFAULT_TARGET_SUBREDDITS
        self.post_limit = DEFAULT_POST_LIMIT
        self.comment_limit = DEFAULT_COMMENT_LIMIT
        self.user_agent = DEFAULT_USER_AGENT

        # Load config early
        self.config = configparser.ConfigParser()
        self.load_config()

    def load_config(self):
        """Loads settings from config.ini."""
        try:
            if os.path.exists(CONFIG_FILE):
                self.config.read(CONFIG_FILE)

                # Read Settings
                self.target_subreddits = self.config.get('Settings', 'Subreddits', fallback=','.join(DEFAULT_TARGET_SUBREDDITS)).split(',')
                self.target_subreddits = [sub.strip() for sub in self.target_subreddits if sub.strip()] # Clean up list
                self.post_limit = self.config.getint('Settings', 'PostLimit', fallback=DEFAULT_POST_LIMIT)
                self.comment_limit = self.config.getint('Settings', 'CommentLimit', fallback=DEFAULT_COMMENT_LIMIT)
                self.user_agent = self.config.get('Credentials', 'UserAgent', fallback=DEFAULT_USER_AGENT)

            else:
                 self.set_status(f"Config file '{CONFIG_FILE}' not found, using defaults.", True, 5)
                 # Use defaults already set

        except Exception as e:
            # Don't crash, just report error and use defaults
            self.set_status(f"Error reading config: {e}", True, 5)
            self.target_subreddits = DEFAULT_TARGET_SUBREDDITS
            self.post_limit = DEFAULT_POST_LIMIT
            self.comment_limit = DEFAULT_COMMENT_LIMIT
            self.user_agent = DEFAULT_USER_AGENT


    def setup_curses(self):
        # ... (same curses setup, add sticky color pair) ...
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.stdscr.timeout(100)

        curses.start_color()
        curses.use_default_colors()

        curses.init_pair(1, COLOR_HIGHLIGHT_FG, COLOR_HIGHLIGHT_BG) # Highlight
        curses.init_pair(2, COLOR_STATUS_FG, COLOR_STATUS_BG)      # Status bar
        curses.init_pair(3, COLOR_TITLE_FG, -1)                    # Titles
        curses.init_pair(4, COLOR_META_FG, -1)                     # Post Metadata
        curses.init_pair(5, COLOR_ERROR_FG, -1)                    # Error Messages
        curses.init_pair(6, COLOR_BORDER_ACTIVE_FG, -1)            # Active Border
        curses.init_pair(7, COLOR_BORDER_INACTIVE_FG, -1)          # Inactive Border
        curses.init_pair(8, COLOR_LINK_FG, -1)                     # Link post indicator
        curses.init_pair(9, COLOR_TEXTPOST_FG, -1)                 # Text post indicator
        curses.init_pair(10, COLOR_COMMENT_FG, -1)                 # Comment Text
        curses.init_pair(11, COLOR_COMMENT_META_FG, -1)            # Comment Metadata
        # Comment depth colors (pairs 12 to 12+N-1)
        for i, color in enumerate(COLOR_COMMENT_DEPTH_FG):
             curses.init_pair(12 + i, color, -1)
        # Sticky indicator color (pair 12+N)
        curses.init_pair(12 + len(COLOR_COMMENT_DEPTH_FG), COLOR_STICKY_FG, -1)
        # Loading indicator color (pair 12+N+1) - reuse title color?
        curses.init_pair(12 + len(COLOR_COMMENT_DEPTH_FG) + 1, COLOR_LOADING_FG, -1)


        self.attr = {
            "highlight": curses.color_pair(1),
            "status": curses.color_pair(2),
            "title": curses.color_pair(3) | curses.A_BOLD,
            "meta": curses.color_pair(4),
            "error": curses.color_pair(5) | curses.A_BOLD,
            "border_active": curses.color_pair(6) | curses.A_BOLD,
            "border_inactive": curses.color_pair(7),
            "link": curses.color_pair(8),
            "textpost": curses.color_pair(9),
            "sticky": curses.color_pair(12 + len(COLOR_COMMENT_DEPTH_FG)) | curses.A_BOLD,
            "loading": curses.color_pair(12 + len(COLOR_COMMENT_DEPTH_FG) + 1) | curses.A_BOLD,
            "comment": curses.color_pair(10),
            "comment_meta": curses.color_pair(11),
            "comment_depth": [curses.color_pair(12 + i) for i in range(len(COLOR_COMMENT_DEPTH_FG))]
        }
        self.attr["normal"] = curses.A_NORMAL


    # ... (keep get_layout, create_windows, set_status, draw_status, draw_pane_border) ...
    def get_layout(self):
        # ... (same as before) ...
        max_h, max_w = self.stdscr.getmaxyx()
        status_h = STATUS_BAR_HEIGHT
        content_h = max_h - status_h
        left_w = max(MIN_LEFT_PANE_WIDTH, int(max_w * LEFT_PANE_WIDTH_RATIO))
        right_w = max_w - left_w
        return content_h, max_h, max_w, left_w, right_w, status_h

    def create_windows(self, content_h, max_w, left_w, right_w, status_h):
        # ... (same as before) ...
        if hasattr(self, 'left_win'): del self.left_win
        if hasattr(self, 'right_win'): del self.right_win
        if hasattr(self, 'status_win'): del self.status_win
        if hasattr(self, 'post_view_win'): del self.post_view_win
        if hasattr(self, 'comment_view_win'): del self.comment_view_win

        self.left_win = curses.newwin(content_h, left_w, 0, 0)
        self.right_win = curses.newwin(content_h, right_w, 0, left_w)
        self.status_win = curses.newwin(status_h, max_w, content_h, 0)
        # Overlapping windows for different views in the right pane area
        self.post_view_win = curses.newwin(content_h, right_w, 0, left_w)
        self.comment_view_win = curses.newwin(content_h, right_w, 0, left_w)

        self.left_win.keypad(True)
        self.right_win.keypad(True)
        self.post_view_win.keypad(True)
        self.comment_view_win.keypad(True)

    def set_status(self, message, temporary=False, duration=2):
        # ... (same as before) ...
        if temporary:
            self.temp_status_message = message
            self.temp_status_timer = time.time() + duration
        else:
            self.status_message = message
            self.temp_status_message = None

    def draw_status(self, max_w):
        # ... (update hints for new 'l' key) ...
        self.status_win.erase()
        self.status_win.bkgd(' ', self.attr["status"])

        current_status = self.status_message
        if self.temp_status_message and time.time() < self.temp_status_timer:
            current_status = self.temp_status_message
        elif self.temp_status_message and time.time() >= self.temp_status_timer:
            self.temp_status_message = None # Expired

        safe_addstr(self.status_win, 0, 0, current_status[:max_w-1], self.attr["status"])

        hints = ""
        if self.current_view == VIEW_LIST:
             hints = "Arrows:Nav|Tab:Pane|Enter:Select|c:Comments|o:Open|r:Refresh|q:Quit"
        elif self.current_view == VIEW_POST:
             hints = "Arrows/PgUp/Dn:Scroll|o:Open Link|q/Esc:Back"
        elif self.current_view == VIEW_COMMENTS:
             hints = "Arrows/PgUp/Dn:Scroll|l:LoadMore|o:Open Post|q/Esc:Back" # Added 'l'

        hints_x = max(1, max_w - len(hints) - 1)
        safe_addstr(self.status_win, 0, hints_x, hints, self.attr["status"])
        try:
            self.status_win.refresh()
        except curses.error: pass

    def draw_pane_border(self, window, title, is_active):
        # ... (same as before) ...
        border_attr = self.attr["border_active"] if is_active else self.attr["border_inactive"]
        title_attr = self.attr["title"]
        window.border(border_attr)
        safe_addstr(window, 0, 2, f" {title} ", title_attr)

    def draw_left_pane(self, h, w):
        # ... (use self.target_subreddits) ...
        self.left_win.erase()
        is_active = self.current_view == VIEW_LIST and self.active_pane == PANE_SUBS
        self.draw_pane_border(self.left_win, "Subreddits", is_active)

        for i in range(h - 2):
            sub_idx = self.sub_scroll_top + i
            if sub_idx >= len(self.target_subreddits): break # Use dynamic list
            sub_name = self.target_subreddits[sub_idx]
            attr = self.attr["normal"]
            prefix = "  "
            if sub_idx == self.current_sub_index:
                attr = self.attr["highlight"]
                prefix = "> "
                if is_active: attr |= curses.A_REVERSE

            safe_addstr(self.left_win, i + 1, 1, f"{prefix}r/{sub_name}", attr)
        try:
            self.left_win.refresh()
        except curses.error: pass

    def draw_right_pane(self, h, w):
        # ... (add sticky indicator) ...
        self.right_win.erase()
        is_active = self.current_view == VIEW_LIST and self.active_pane == PANE_POSTS
        selected_sub = self.target_subreddits[self.current_sub_index]
        self.draw_pane_border(self.right_win, f"r/{selected_sub}", is_active)

        current_posts = self.posts.get(selected_sub, [])
        y_pos = 1

        if not current_posts and selected_sub not in self.last_fetch_time:
             msg = "(Press Enter in left pane to load)"
             attr = self.attr["normal"]
             safe_addstr(self.right_win, y_pos, 2, msg, attr)
        elif not current_posts and selected_sub in self.last_fetch_time:
             msg = "(No posts found or error)"
             attr = self.attr["error"]
             safe_addstr(self.right_win, y_pos, 2, msg, attr)
        else:
            for i in range(h - 2):
                post_idx = self.post_scroll_top + i
                if post_idx >= len(current_posts) or y_pos >= h - 1: break

                post = current_posts[post_idx]
                attr = self.attr["normal"]
                prefix = "  "
                if post_idx == self.current_post_index:
                    attr = self.attr["highlight"]
                    prefix = "> "
                    if is_active: attr |= curses.A_REVERSE

                try:
                    author = f"u/{post.author.name}" if post.author else "[deleted]"
                    score = post.score
                    comments = post.num_comments
                    time_str = format_timestamp(post.created_utc)
                    title = post.title
                    post_type_attr = self.attr["link"] if not post.is_self else self.attr["textpost"]
                    post_type_indicator = "[L]" if not post.is_self else "[T]"
                    sticky_indicator = "[S]" if post.stickied else "" # Sticky Check

                    # Line 1: Title
                    title_line = f"{prefix}{title}"
                    safe_addstr(self.right_win, y_pos, 1, title_line, attr)

                    # Line 2: Metadata + Type/Sticky Indicator
                    meta_line = f"  {score:>4}pts {comments:>3}c {author:<15} {time_str}"
                    safe_addstr(self.right_win, y_pos + 1, 1, meta_line, self.attr["meta"])
                    # Combine indicators
                    indicators = f"{sticky_indicator}{post_type_indicator}"
                    indicator_x = w - len(indicators) - 2
                    if post.stickied: # Draw sticky part in sticky color
                         safe_addstr(self.right_win, y_pos + 1, indicator_x, sticky_indicator, self.attr["sticky"])
                         safe_addstr(self.right_win, y_pos + 1, indicator_x + len(sticky_indicator), post_type_indicator, post_type_attr)
                    else: # Just draw type indicator
                         safe_addstr(self.right_win, y_pos + 1, indicator_x, post_type_indicator, post_type_attr)

                    y_pos += 2

                except Exception:
                     safe_addstr(self.right_win, y_pos, 1, f"{prefix}[Error displaying post info]", self.attr["error"])
                     y_pos += 1
        try:
            self.right_win.refresh()
        except curses.error: pass


    def draw_post_view(self, h, w):
        # ... (minor refinements maybe, mostly the same) ...
        self.post_view_win.erase()
        self.draw_pane_border(self.post_view_win, "Post View", True)

        selected_sub = self.target_subreddits[self.current_sub_index]
        current_posts = self.posts.get(selected_sub, [])
        if not current_posts or self.current_post_index >= len(current_posts):
            safe_addstr(self.post_view_win, 1, 2, "Error: Post not available.", self.attr["error"])
            self.post_view_win.refresh(); return

        post = current_posts[self.current_post_index]
        try:
            author = f"u/{post.author.name}" if post.author else "[deleted]"
            meta_line = f"{post.score}pts | {post.num_comments}c | {author} | {format_timestamp(post.created_utc)} | r/{post.subreddit.display_name}"
            safe_addstr(self.post_view_win, 1, 2, post.title, self.attr["title"])
            safe_addstr(self.post_view_win, 2, 2, meta_line, self.attr["meta"])
            self.post_view_win.hline(3, 1, '-', w - 2)

            content_to_display = post.selftext if post.is_self else f"Link Post URL:\n{post.url}"
            lines = []
            if content_to_display:
                 for paragraph in content_to_display.split('\n'):
                     lines.extend(textwrap.wrap(paragraph, width=w - 4, replace_whitespace=False, drop_whitespace=False))

            content_h = h - 5
            for i in range(content_h):
                line_idx = self.post_content_scroll_top + i
                if line_idx >= len(lines): break
                safe_addstr(self.post_view_win, i + 4, 2, lines[line_idx])

            if len(lines) > content_h:
                scroll_perc = int(100 * (self.post_content_scroll_top + min(content_h, len(lines)-self.post_content_scroll_top)) / len(lines)) if len(lines) > 0 else 0
                indicator = f"[{scroll_perc}%]"
                safe_addstr(self.post_view_win, h - 1, w - len(indicator) - 2, indicator)

        except Exception as e:
             safe_addstr(self.post_view_win, 1, 2, f"Error displaying post: {e}", self.attr["error"])
        try:
            self.post_view_win.refresh()
        except curses.error: pass


    def draw_comments_view(self, h, w):
        # ... (Major changes for selection highlight and Load More text) ...
        self.comment_view_win.erase()
        selected_sub = self.target_subreddits[self.current_sub_index]
        post = self.posts.get(selected_sub, [])[self.current_post_index]
        self.draw_pane_border(self.comment_view_win, f"Comments: {post.title[:w-20]}", True)

        post_id = post.id
        current_comments = self.comments.get(post_id, None) # Use None to distinguish not loaded vs empty
        y_pos = 1

        if current_comments is None and post_id not in self.last_fetch_time:
             # Not loaded yet, show initial loading message
             msg = "(Press 'c' in post list to load comments)"
             safe_addstr(self.comment_view_win, y_pos, 2, msg, self.attr["normal"])
        elif current_comments is None and post_id in self.last_fetch_time:
             # Fetch initiated but maybe not complete? Or actual error occurred?
             msg = "(Loading comments...)" # Assume loading if fetch was tried
             # Check if self.comments contains an empty list specifically for error case
             if post_id in self.comments and self.comments[post_id] == []:
                 msg = "(No comments found or error)"
             safe_addstr(self.comment_view_win, y_pos, 2, msg, self.attr["normal"])
        elif not current_comments: # Loaded, but empty
             msg = "(No comments found)"
             safe_addstr(self.comment_view_win, y_pos, 2, msg, self.attr["normal"])

        else: # Comments exist, draw them
             # Generate or retrieve cached flattened list of drawable lines
             flat_comment_lines = self._get_or_create_comment_lines(post_id, current_comments, w)

             # Draw visible lines from the flattened list
             for i in range(h - 2):
                 line_idx = self.comment_scroll_top + i
                 if line_idx >= len(flat_comment_lines): break

                 line_info = flat_comment_lines[line_idx]
                 comment_obj = line_info['obj']
                 line_text = line_info['line']
                 line_in_comment_idx = line_info['idx']
                 original_comment_idx = line_info['c_idx']

                 # Determine highlighting based on selected comment *object* index
                 is_selected_comment = (original_comment_idx == self.current_comment_index)
                 line_attr = self.attr["comment"] # Default

                 if isinstance(comment_obj, praw.models.MoreComments):
                      line_attr = self.attr["meta"] # Style 'Load More' differently
                      # Make Load More text clearer
                      line_text = f"{'  ' * comment_obj.depth}>>> Load More ({comment_obj.count}) Press 'l' <<<"
                 elif line_in_comment_idx == 0: # Meta line
                      line_attr = self.attr["comment_meta"]
                      # Add depth indicator color
                      depth_color_idx = comment_obj.depth % len(self.attr["comment_depth"])
                      depth_attr = self.attr["comment_depth"][depth_color_idx]
                      safe_addstr(self.comment_view_win, y_pos + i, 1, '|', depth_attr)

                 # Apply highlight background to ALL lines of the selected comment
                 if is_selected_comment:
                     # Get current fg color from attr pair
                     fg_color = curses.pair_content(line_attr)[0] if curses.has_colors() else COLOR_HIGHLIGHT_FG
                     # Use highlight bg with original fg color
                     curses.init_pair(20, fg_color, COLOR_HIGHLIGHT_BG) # Use a temp pair number
                     line_attr = curses.color_pair(20)


                 safe_addstr(self.comment_view_win, y_pos + i, 2, line_text, line_attr)

             # Scroll indicator
             if len(flat_comment_lines) > h - 2:
                 scroll_perc = int(100 * (self.comment_scroll_top + min(h - 2, len(flat_comment_lines)-self.comment_scroll_top)) / len(flat_comment_lines)) if len(flat_comment_lines) > 0 else 0
                 indicator = f"[{scroll_perc}%]"
                 safe_addstr(self.comment_view_win, h - 1, w - len(indicator) - 2, indicator)

        try:
            self.comment_view_win.refresh()
        except curses.error: pass


    def _get_or_create_comment_lines(self, post_id, comments_list, width):
        """Generates or retrieves cached list of comment lines for drawing."""
        if hasattr(self, '_comment_lines_cache') and self._comment_lines_cache['post_id'] == post_id:
            return self._comment_lines_cache['lines']

        # Generate new list
        flat_list = []
        wrap_width = width - 4 # Width available for text wrapping
        for c_idx, comment in enumerate(comments_list):
              if isinstance(comment, praw.models.MoreComments):
                  # Placeholder text is handled during drawing now
                  flat_list.append({'obj': comment, 'line': "", 'idx': 0, 'c_idx': c_idx})
                  continue

              try:
                    indent = "  " * comment.depth
                    author = f"u/{comment.author.name}" if comment.author else "[deleted]"
                    meta = f"{indent}{author} | {comment.score}pts | {format_timestamp(comment.created_utc)}"
                    body = comment.body if comment.body else ""

                    # Wrap body
                    wrapped_body_lines = []
                    for paragraph in body.split('\n'):
                        wrapped_body_lines.extend(textwrap.wrap(paragraph, width=wrap_width,
                                                                 replace_whitespace=False, drop_whitespace=False,
                                                                 initial_indent=indent, subsequent_indent=indent))

                    # Add meta line first, then body lines
                    flat_list.append({'obj': comment, 'line': meta, 'idx': 0, 'c_idx': c_idx})
                    for l_idx, line in enumerate(wrapped_body_lines):
                        flat_list.append({'obj': comment, 'line': line, 'idx': l_idx + 1, 'c_idx': c_idx})
              except Exception:
                    flat_list.append({'obj': comment, 'line': f"{indent}[Error displaying comment]", 'idx': 0, 'c_idx': c_idx})

        self._comment_lines_cache = {'post_id': post_id, 'lines': flat_list}
        return flat_list


    def draw_ui(self):
        # ... (same as before) ...
        content_h, max_h, max_w, left_w, right_w, status_h = self.get_layout()
        self.stdscr.erase()
        self.stdscr.refresh()

        if max_h < 5 or max_w < 30:
            self.stdscr.addstr(0, 0, "Terminal too small")
            return

        self.draw_status(max_w)

        if self.current_view == VIEW_LIST:
            self.draw_left_pane(content_h, left_w)
            self.draw_right_pane(content_h, right_w)
        elif self.current_view == VIEW_POST:
            self.draw_left_pane(content_h, left_w)
            self.draw_post_view(content_h, right_w)
        elif self.current_view == VIEW_COMMENTS:
            self.draw_left_pane(content_h, left_w)
            self.draw_comments_view(content_h, right_w)


    def handle_resize(self):
        # ... (same as before) ...
        content_h, max_h, max_w, left_w, right_w, status_h = self.get_layout()
        curses.resizeterm(max_h, max_w)
        self.create_windows(content_h, max_w, left_w, right_w, status_h)
        if hasattr(self, '_comment_lines_cache'): del self._comment_lines_cache
        self.draw_ui()

    # --- Authentication & Data Fetching ---

    def authenticate(self):
        """Authenticates using config file or prompts."""
        client_id = None
        client_secret = None
        username = None
        password = None

        try:
            if self.config.has_section('Credentials'):
                client_id = self.config.get('Credentials', 'ClientID', fallback=None)
                client_secret = self.config.get('Credentials', 'ClientSecret', fallback=None)
                username = self.config.get('Credentials', 'Username', fallback=None)
                password = self.config.get('Credentials', 'Password', fallback=None)
                # User agent already loaded in load_config

            if not all([client_id, client_secret, username, password, self.user_agent]):
                print(f"INFO: Credentials missing in {CONFIG_FILE} or invalid. Falling back to prompts.")
                client_id = input("Enter Reddit Client ID: ")
                client_secret = input("Enter Reddit Client Secret: ")
                username = input("Enter Reddit Username: ")
                password = getpass.getpass("Enter Reddit Password: ")
                if not self.user_agent or self.user_agent == DEFAULT_USER_AGENT:
                     self.user_agent = input("Enter User Agent (e.g., MyScript/1.0 by YourUsername): ")


            print("Authenticating with Reddit...")
            self.reddit = praw.Reddit(
                client_id=client_id.strip(),
                client_secret=client_secret.strip(),
                user_agent=self.user_agent.strip(),
                username=username.strip(),
                password=password.strip(),
                check_for_async=False
            )
            user_me = self.reddit.user.me()
            if user_me is None: raise praw.exceptions.AuthenticationException("Authentication failed, user is None.")
            print(f"Authentication successful as u/{user_me.name}")
            self.set_status(f"u/{user_me.name} | Select subreddit and press Enter")
            return True

        except configparser.Error as e:
             print(f"\n[ERROR] Config file error: {e}")
             self.set_status(f"Config file error: {e}")
             time.sleep(3); return False
        except praw.exceptions.PRAWException as e:
             print(f"\n[ERROR] Reddit API/Auth Error: {e}")
             self.set_status(f"Reddit API/Auth Error: {e}")
             time.sleep(3); return False
        except Exception as e:
             print(f"\n[ERROR] Authentication Failed: {e}")
             self.set_status(f"Authentication Failed: {e}")
             time.sleep(3); return False

    def fetch_posts(self, sub_name):
        if not self.reddit: self.set_status("Error: Not authenticated.", True); return
        # Show loading indicator
        draw_loading_pane(self.right_win, f"Fetching r/{sub_name}...")
        self.set_status(f"Fetching posts for r/{sub_name}...")

        try:
            subreddit = self.reddit.subreddit(sub_name)
            fetched_posts = list(subreddit.new(limit=self.post_limit)) # Use config limit
            self.posts[sub_name] = fetched_posts
            self.last_fetch_time[sub_name] = time.time()
            self.set_status(f"Loaded {len(fetched_posts)} posts from r/{sub_name}.")
            self.current_post_index = 0
            self.post_scroll_top = 0
        except praw.exceptions.PRAWException as e:
             self.posts[sub_name] = []
             self.set_status(f"Error fetching r/{sub_name}: {e}", True)
        except Exception as e:
             self.posts[sub_name] = []
             self.set_status(f"Unexpected error fetching r/{sub_name}: {e}", True)
        # No finally needed, draw_ui in main loop will redraw correctly


    def fetch_comments(self, post, replace_more_count=0):
        """Fetches comments, optionally replacing MoreComments objects."""
        if not self.reddit: self.set_status("Error: Not authenticated.", True); return

        post_id = post.id
        # Show loading indicator in comment pane
        draw_loading_pane(self.comment_view_win, f"Fetching comments...")
        self.set_status(f"Fetching comments for {post_id}...")
        self.comments[post_id] = None # Indicate loading started

        try:
            # Fetch the submission again to ensure we have the latest comment tree state
            submission = self.reddit.submission(id=post_id)
            if replace_more_count > 0:
                # Replace *some* MoreComments objects
                submission.comments.replace_more(limit=replace_more_count)
            else:
                 # Just get top-level, don't replace any MoreComments automatically
                 submission.comments.replace_more(limit=0)

            fetched_comments = submission.comments.list()
            self.comments[post_id] = fetched_comments
            self.last_fetch_time[post_id] = time.time()
            if hasattr(self, '_comment_lines_cache'): del self._comment_lines_cache # Invalidate cache
            self.set_status(f"Loaded {len(fetched_comments)} comment items.")
            # Reset scroll/selection only if it was the initial fetch
            if replace_more_count == 0:
                 self.current_comment_index = 0
                 self.comment_scroll_top = 0

        except praw.exceptions.PRAWException as e:
             self.comments[post_id] = [] # Set to empty list on error
             self.set_status(f"Error fetching comments: {e}", True)
        except Exception as e:
             self.comments[post_id] = []
             self.set_status(f"Unexpected error fetching comments: {e}", True)


    def open_link_in_browser(self, url):
         # ... (same as before) ...
         try:
             webbrowser.open(url)
             self.set_status(f"Opened: {url[:60]}...", True)
         except Exception as e:
             self.set_status(f"Failed to open link: {e}", True)

    # --- Input Handling ---
    # ... (Refactor input handling methods, especially comments) ...

    def _handle_list_input(self, key):
        # ... (use self.target_subreddits, self.post_limit) ...
        sub_name = self.target_subreddits[self.current_sub_index]
        current_posts = self.posts.get(sub_name, [])
        lh, lw = self.left_win.getmaxyx()
        rh, rw = self.right_win.getmaxyx()
        num_subs = len(self.target_subreddits)
        num_posts = len(current_posts)
        lines_per_post_entry = 2

        # --- Basic Movement ---
        if key == curses.KEY_DOWN or key == ord('j'):
            # ... (logic mostly same, just uses num_subs/num_posts) ...
            if self.active_pane == PANE_SUBS:
                if self.current_sub_index < num_subs - 1:
                    self.current_sub_index += 1
                    if self.current_sub_index >= self.sub_scroll_top + lh - 2: self.sub_scroll_top += 1
            else:
                if num_posts > 0 and self.current_post_index < num_posts - 1:
                    self.current_post_index += 1
                    visible_posts_area_h = rh - 2
                    # Ensure post_scroll_top doesn't go beyond possible visible area
                    max_visible_posts = max(1, visible_posts_area_h // lines_per_post_entry)
                    if self.current_post_index >= self.post_scroll_top + max_visible_posts:
                         self.post_scroll_top += 1

        elif key == curses.KEY_UP or key == ord('k'):
            # ... (logic mostly same) ...
            if self.active_pane == PANE_SUBS:
                if self.current_sub_index > 0:
                    self.current_sub_index -= 1
                    if self.current_sub_index < self.sub_scroll_top: self.sub_scroll_top -= 1
            else:
                 if num_posts > 0 and self.current_post_index > 0:
                    self.current_post_index -= 1
                    if self.current_post_index < self.post_scroll_top:
                        self.post_scroll_top -= 1

        # --- Page/Home/End ---
        elif key == curses.KEY_NPAGE: # Page Down
            if self.active_pane == PANE_SUBS:
                 scroll_amount = max(1, lh - 3)
                 new_idx = min(num_subs - 1, self.current_sub_index + scroll_amount)
                 self.sub_scroll_top = min(max(0, num_subs - (lh-2)), self.sub_scroll_top + (new_idx - self.current_sub_index))
                 self.current_sub_index = new_idx
            else:
                 visible_posts_count = max(1, (rh - 2) // lines_per_post_entry)
                 scroll_amount = max(1, visible_posts_count -1)
                 new_idx = min(num_posts - 1, self.current_post_index + scroll_amount)
                 self.post_scroll_top = min(max(0, num_posts - visible_posts_count), self.post_scroll_top + (new_idx - self.current_post_index))
                 self.current_post_index = new_idx

        elif key == curses.KEY_PPAGE: # Page Up
             if self.active_pane == PANE_SUBS:
                 scroll_amount = max(1, lh - 3)
                 new_idx = max(0, self.current_sub_index - scroll_amount)
                 self.sub_scroll_top = max(0, self.sub_scroll_top - (self.current_sub_index - new_idx))
                 self.current_sub_index = new_idx
             else:
                 visible_posts_count = max(1, (rh - 2) // lines_per_post_entry)
                 scroll_amount = max(1, visible_posts_count -1)
                 new_idx = max(0, self.current_post_index - scroll_amount)
                 self.post_scroll_top = max(0, self.post_scroll_top - (self.current_post_index - new_idx))
                 self.current_post_index = new_idx

        elif key == curses.KEY_HOME:
             if self.active_pane == PANE_SUBS:
                 self.current_sub_index = 0; self.sub_scroll_top = 0
             else:
                 self.current_post_index = 0; self.post_scroll_top = 0
        elif key == curses.KEY_END:
            if self.active_pane == PANE_SUBS:
                 self.current_sub_index = num_subs - 1
                 self.sub_scroll_top = max(0, num_subs - (lh - 2))
            else:
                 if num_posts > 0:
                     visible_posts_count = max(1, (rh - 2) // lines_per_post_entry)
                     self.current_post_index = num_posts - 1
                     self.post_scroll_top = max(0, num_posts - visible_posts_count)

        # --- Actions ---
        elif key == ord('\t'):
            self.active_pane = 1 - self.active_pane
            self.set_status(f"Pane: {'Posts' if self.active_pane else 'Subreddits'}")
        elif key == ord('\n') or key == curses.KEY_ENTER:
            if self.active_pane == PANE_SUBS:
                self.fetch_posts(sub_name)
                self.active_pane = PANE_POSTS
            else:
                 if num_posts > 0:
                    self.current_view = VIEW_POST
                    self.post_content_scroll_top = 0
                    self.set_status(f"Viewing Post")
        elif key == ord('c'):
             if self.active_pane == PANE_POSTS and num_posts > 0:
                 post = current_posts[self.current_post_index]
                 self.current_view = VIEW_COMMENTS
                 self.fetch_comments(post) # Initial fetch (limit=0)
                 self.set_status(f"Loading Comments")
             else:
                 self.set_status("Select post first (Tab -> Select)", True)
        elif key == ord('o'):
             if self.active_pane == PANE_POSTS and num_posts > 0:
                 post = current_posts[self.current_post_index]
                 self.open_link_in_browser(post.url)
             else:
                 self.set_status("Select post first (Tab -> Select)", True)
        elif key == ord('r'):
            self.fetch_posts(sub_name)
            self.active_pane = PANE_POSTS
        elif key == ord('q'): return False # Quit

        return True

    def _handle_post_view_input(self, key):
        # ... (mostly same as before) ...
        ph, pw = self.post_view_win.getmaxyx()
        content_h = ph - 5
        sub_name = self.target_subreddits[self.current_sub_index]
        post = self.posts.get(sub_name, [])[self.current_post_index]
        content_to_display = post.selftext if post.is_self else f"Link: {post.url}"
        lines = []
        if content_to_display:
            for paragraph in content_to_display.split('\n'):
                 lines.extend(textwrap.wrap(paragraph, width=pw - 4, replace_whitespace=False, drop_whitespace=False))
        num_lines = len(lines)

        if key == ord('q') or key == 27:
            self.current_view = VIEW_LIST
            self.set_status(f"r/{sub_name}")
        elif key == curses.KEY_DOWN or key == ord('j'):
            if self.post_content_scroll_top < max(0, num_lines - content_h): self.post_content_scroll_top += 1
        elif key == curses.KEY_UP or key == ord('k'):
            if self.post_content_scroll_top > 0: self.post_content_scroll_top -= 1
        elif key == curses.KEY_NPAGE:
            scroll_amount = max(1, content_h - 1)
            self.post_content_scroll_top = min(max(0, num_lines - content_h), self.post_content_scroll_top + scroll_amount)
        elif key == curses.KEY_PPAGE:
            scroll_amount = max(1, content_h - 1)
            self.post_content_scroll_top = max(0, self.post_content_scroll_top - scroll_amount)
        elif key == curses.KEY_HOME:
            self.post_content_scroll_top = 0
        elif key == curses.KEY_END:
             self.post_content_scroll_top = max(0, num_lines - content_h)
        elif key == ord('o'):
             self.open_link_in_browser(f"https://reddit.com{post.permalink}" if post.is_self else post.url)

        return True

    def _handle_comments_view_input(self, key):
        # --- Navigation based on comment *objects* first ---
        sub_name = self.target_subreddits[self.current_sub_index]
        post = self.posts.get(sub_name, [])[self.current_post_index]
        current_comments = self.comments.get(post.id, []) # The list of comment objects
        num_comments = len(current_comments)

        # Get window dimensions
        ch, cw = self.comment_view_win.getmaxyx()
        content_h = ch - 2 # Visible lines for comments

        # Keep track of the first visible line index for the selected comment
        selected_comment_start_line = -1
        if hasattr(self, '_comment_lines_cache') and self._comment_lines_cache['post_id'] == post.id:
            flat_lines = self._comment_lines_cache['lines']
            for line_idx, line_info in enumerate(flat_lines):
                 if line_info['c_idx'] == self.current_comment_index:
                      selected_comment_start_line = line_idx
                      break

        if key == curses.KEY_DOWN or key == ord('j'):
            if self.current_comment_index < num_comments - 1:
                 self.current_comment_index += 1
                 # Auto-scroll down to keep the newly selected comment visible
                 if selected_comment_start_line != -1:
                     # Find the start line of the *new* selected comment
                     new_selected_start_line = -1
                     for line_idx, line_info in enumerate(flat_lines):
                          if line_info['c_idx'] == self.current_comment_index:
                               new_selected_start_line = line_idx
                               break
                     if new_selected_start_line >= self.comment_scroll_top + content_h:
                          self.comment_scroll_top = new_selected_start_line - content_h + 1 # Scroll just enough
                     elif new_selected_start_line < self.comment_scroll_top: # Should not happen on down? Safety.
                          self.comment_scroll_top = new_selected_start_line

        elif key == curses.KEY_UP or key == ord('k'):
             if self.current_comment_index > 0:
                 self.current_comment_index -= 1
                 # Auto-scroll up
                 if selected_comment_start_line != -1:
                      # Find the start line of the *new* selected comment
                     new_selected_start_line = -1
                     for line_idx, line_info in enumerate(flat_lines):
                          if line_info['c_idx'] == self.current_comment_index:
                               new_selected_start_line = line_idx
                               break
                     if new_selected_start_line < self.comment_scroll_top:
                          self.comment_scroll_top = new_selected_start_line

        # --- Scrolling based on lines (PgUp/PgDn/Home/End now scroll the view) ---
        elif key == curses.KEY_NPAGE:
             if hasattr(self, '_comment_lines_cache'):
                 num_lines = len(self._comment_lines_cache['lines'])
                 scroll_amount = max(1, content_h - 1)
                 self.comment_scroll_top = min(max(0, num_lines - content_h), self.comment_scroll_top + scroll_amount)
        elif key == curses.KEY_PPAGE:
             if hasattr(self, '_comment_lines_cache'):
                 scroll_amount = max(1, content_h - 1)
                 self.comment_scroll_top = max(0, self.comment_scroll_top - scroll_amount)
        elif key == curses.KEY_HOME:
             self.comment_scroll_top = 0
             self.current_comment_index = 0 # Also select first comment
        elif key == curses.KEY_END:
             if hasattr(self, '_comment_lines_cache'):
                 num_lines = len(self._comment_lines_cache['lines'])
                 self.comment_scroll_top = max(0, num_lines - content_h)
                 # Select last comment object
                 if current_comments: self.current_comment_index = len(current_comments) - 1

        # --- Actions ---
        elif key == ord('l'): # Load More Comments
            if current_comments and self.current_comment_index < num_comments:
                selected_comment = current_comments[self.current_comment_index]
                if isinstance(selected_comment, praw.models.MoreComments):
                     # Fetch again, but request replacements
                     self.fetch_comments(post, replace_more_count=10) # Fetch and replace some
                     self.set_status("Attempting to load more comments...", True)
                else:
                     self.set_status("Not a 'Load More' item.", True)
            else:
                self.set_status("No comment selected?", True)

        elif key == ord('o'):
             self.open_link_in_browser(f"https://reddit.com{post.permalink}") # Always open post permalink
        elif key == ord('q') or key == 27:
            self.current_view = VIEW_LIST
            self.set_status(f"r/{sub_name}")

        # Ensure scroll top is valid after potential list changes
        if hasattr(self, '_comment_lines_cache'):
             num_lines = len(self._comment_lines_cache['lines'])
             self.comment_scroll_top = max(0, min(self.comment_scroll_top, num_lines - content_h))


        return True

    def run(self):
        # Create default config if it doesn't exist
        if not os.path.exists(CONFIG_FILE):
            self._create_default_config()

        if not self.authenticate():
             print("\nAuthentication failed. Please check credentials in config.ini or prompts.")
             print("If using config.ini, ensure it exists and is correctly formatted.")
             return # Exit if auth failed

        try:
            curses.wrapper(self._run_curses)
        except curses.error as e:
             curses.endwin()
             print(f"\nCurses Error: {e}")
             print("Your terminal might not fully support curses features or colors.")
        except Exception as e:
            curses.endwin()
            print(f"\nAn unexpected error occurred: {e}")
            import traceback
            traceback.print_exc()


    def _run_curses(self, stdscr):
        # ... (main loop logic same as before) ...
        self.stdscr = stdscr
        self.setup_curses()
        content_h, max_h, max_w, left_w, right_w, status_h = self.get_layout()
        self.create_windows(content_h, max_w, left_w, right_w, status_h)

        running = True
        while running:
            try:
                self.draw_ui()
                key = self.stdscr.getch() # Get input

                # Handle global keys first
                if key == curses.KEY_RESIZE:
                    self.handle_resize()
                    continue

                # Handle view-specific keys
                if self.current_view == VIEW_LIST:
                    running = self._handle_list_input(key)
                elif self.current_view == VIEW_POST:
                    running = self._handle_post_view_input(key)
                elif self.current_view == VIEW_COMMENTS:
                    running = self._handle_comments_view_input(key)

            except curses.error as e:
                 # Handle potential curses errors gracefully during loop
                 self.set_status(f"Curses rendering error: {e}", True, 5)
            except Exception as e:
                 # Catch other unexpected errors during the loop
                 curses.endwin() # Try to clean up terminal
                 print(f"\nRuntime Error: {e}")
                 import traceback
                 traceback.print_exc()
                 running = False # Exit loop

    def _create_default_config(self):
        """Creates a default config.ini if one doesn't exist."""
        if os.path.exists(CONFIG_FILE): return

        print(f"INFO: Configuration file '{CONFIG_FILE}' not found. Creating a default one.")
        print("INFO: Please edit it with your Reddit API credentials and preferences.")

        config = configparser.ConfigParser()
        config['Credentials'] = {
            'ClientID': 'YOUR_CLIENT_ID_HERE',
            'ClientSecret': 'YOUR_CLIENT_SECRET_HERE',
            'Username': 'YOUR_REDDIT_USERNAME',
            'Password': 'YOUR_REDDIT_PASSWORD',
            'UserAgent': f'CursesRedditClient/0.3 by YOUR_REDDIT_USERNAME'
        }
        config['Settings'] = {
            'Subreddits': ', '.join(DEFAULT_TARGET_SUBREDDITS),
            'PostLimit': str(DEFAULT_POST_LIMIT),
            'CommentLimit': str(DEFAULT_COMMENT_LIMIT)
        }
        try:
            with open(CONFIG_FILE, 'w') as configfile:
                config.write(configfile)
            print(f"INFO: Default '{CONFIG_FILE}' created successfully.")
            print("INFO: Exiting now. Please edit the file and restart.")
            sys.exit(0) # Exit after creating config so user can edit it
        except IOError as e:
            print(f"ERROR: Could not write default config file: {e}")
            # Don't exit, will proceed with prompts or defaults

# --- Run the app ---
if __name__ == "__main__":
    if os.name == 'nt':
        try: import windows_curses
        except ImportError: print("Please install 'windows-curses'"); sys.exit(1)

    app = RedditCursesApp(None)
    app.run()
