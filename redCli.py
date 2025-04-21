import curses
import praw
import getpass
import textwrap
import time
from datetime import datetime
import webbrowser # For opening links
import threading # For potential future non-blocking fetch
import queue # For potential future non-blocking fetch
import os
# --- Configuration ---
TARGET_SUBREDDITS = ["Bard", "LocalLLaMA"]
POST_LIMIT = 20 # Fetch more posts for scrolling
COMMENT_LIMIT = 50 # Max comments to fetch initially (PRAW handles loading more if needed)
CLIENT_ID = "your-id"
CLIENT_SECRET = "your-secret"
USER_AGENT = "CursesRedditClient/0.2 by samunder" # !!! CHANGE YourUsername !!!
USERNAME = "your-username"
PASSWORD = "your-passwd"

# --- Constants ---
LEFT_PANE_WIDTH_RATIO = 0.30
MIN_LEFT_PANE_WIDTH = 20
STATUS_BAR_HEIGHT = 1

# Views
VIEW_LIST = 0       # Subreddit/Post list view
VIEW_POST = 1       # Reading a single post's selftext/URL
VIEW_COMMENTS = 2   # Reading comments for a post

# Panes (for VIEW_LIST)
PANE_SUBS = 0
PANE_POSTS = 1

# Colors (adjust as desired)
COLOR_HIGHLIGHT_BG = curses.COLOR_BLUE
COLOR_HIGHLIGHT_FG = curses.COLOR_WHITE
COLOR_STATUS_BG = curses.COLOR_BLUE
COLOR_STATUS_FG = curses.COLOR_WHITE
COLOR_TITLE_FG = curses.COLOR_YELLOW
COLOR_META_FG = curses.COLOR_CYAN
COLOR_BORDER_ACTIVE_FG = curses.COLOR_WHITE
COLOR_BORDER_INACTIVE_FG = curses.COLOR_BLUE # Dimmer border for inactive pane
COLOR_LINK_FG = curses.COLOR_GREEN
COLOR_TEXTPOST_FG = curses.COLOR_WHITE
COLOR_ERROR_FG = curses.COLOR_RED
COLOR_COMMENT_FG = curses.COLOR_WHITE # Base comment color
COLOR_COMMENT_META_FG = curses.COLOR_YELLOW
COLOR_COMMENT_DEPTH_FG = [curses.COLOR_CYAN, curses.COLOR_GREEN, curses.COLOR_MAGENTA, curses.COLOR_BLUE] # Cycle colors for depth

# --- Helper Functions ---
def format_timestamp(timestamp_utc):
    now = datetime.utcnow()
    dt_object = datetime.utcfromtimestamp(timestamp_utc)
    delta = now - dt_object
    seconds = delta.total_seconds()

    if seconds < 60: return f"{int(seconds)}s ago"
    if seconds < 3600: return f"{int(seconds / 60)}m ago"
    if seconds < 86400: return f"{int(seconds / 3600)}h ago"
    return f"{int(seconds / 86400)}d ago"

def safe_addstr(window, y, x, text, attr=0):
    try:
        h, w = window.getmaxyx()
        if y >= h or x >= w or y < 0 or x < 0: return
        available_width = w - x
        if available_width <= 0: return
        # Simple truncate - potentially breaks unicode, but safer for basic curses
        truncated_text = text.replace('\n', ' ').replace('\r', '')[:available_width]
        window.addstr(y, x, truncated_text, attr)
    except curses.error:
        pass # Ignore errors writing to edges etc.
    except Exception:
        pass # Ignore other potential errors

# --- Main Application Class ---
class RedditCursesApp:
    def __init__(self, stdscr):
        self.stdscr = stdscr
        self.reddit = None
        self.current_view = VIEW_LIST
        self.active_pane = PANE_SUBS # 0: Left (Subreddits), 1: Right (Posts)

        # Data storage
        self.posts = {} # Cache: {sub_name: [post1, post2,...]}
        self.comments = {} # Cache: {post_id: [comment1, comment2,...]}
        self.current_sub_index = 0
        self.current_post_index = 0
        self.current_comment_index = 0
        self.sub_scroll_top = 0
        self.post_scroll_top = 0
        self.post_content_scroll_top = 0
        self.comment_scroll_top = 0

        self.status_message = "Initializing..."
        self.temp_status_message = None # For temporary messages
        self.temp_status_timer = 0
        self.last_fetch_time = {}

        # For potential future async fetching
        # self.fetch_queue = queue.Queue()
        # self.result_queue = queue.Queue()

    def setup_curses(self):
        curses.curs_set(0)
        self.stdscr.nodelay(1)
        self.stdscr.timeout(100) # Refresh ~10 times/sec for responsiveness

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
        # Comment depth colors
        for i, color in enumerate(COLOR_COMMENT_DEPTH_FG):
             curses.init_pair(12 + i, color, -1)


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
            "comment": curses.color_pair(10),
            "comment_meta": curses.color_pair(11),
            "comment_depth": [curses.color_pair(12 + i) for i in range(len(COLOR_COMMENT_DEPTH_FG))]
        }
        self.attr["normal"] = curses.A_NORMAL

    def get_layout(self):
        max_h, max_w = self.stdscr.getmaxyx()
        status_h = STATUS_BAR_HEIGHT
        content_h = max_h - status_h
        left_w = max(MIN_LEFT_PANE_WIDTH, int(max_w * LEFT_PANE_WIDTH_RATIO))
        right_w = max_w - left_w
        return content_h, max_h, max_w, left_w, right_w, status_h

    def create_windows(self, content_h, max_w, left_w, right_w, status_h):
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
        """Sets the status message, optionally temporarily."""
        if temporary:
            self.temp_status_message = message
            self.temp_status_timer = time.time() + duration
        else:
            self.status_message = message
            self.temp_status_message = None # Clear temporary message

    def draw_status(self, max_w):
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
             hints = "Arrows:Nav | Tab:Pane | Enter:Select | c:Comments | o:Open | r:Refresh | q:Quit"
        elif self.current_view == VIEW_POST:
             hints = "Arrows/PgUp/Dn:Scroll | o:Open Link | q/Esc:Back"
        elif self.current_view == VIEW_COMMENTS:
             hints = "Arrows/PgUp/Dn:Scroll | o:Open Post Link | q/Esc:Back"

        hints_x = max(1, max_w - len(hints) - 1)
        safe_addstr(self.status_win, 0, hints_x, hints, self.attr["status"])
        try:
            self.status_win.refresh()
        except curses.error: pass # Ignore occasional refresh errors

    def draw_pane_border(self, window, title, is_active):
        """Draws the border and title, styled based on active state."""
        border_attr = self.attr["border_active"] if is_active else self.attr["border_inactive"]
        title_attr = self.attr["title"] # Keep title color consistent
        window.border(border_attr)
        safe_addstr(window, 0, 2, f" {title} ", title_attr)


    def draw_left_pane(self, h, w):
        self.left_win.erase()
        is_active = self.current_view == VIEW_LIST and self.active_pane == PANE_SUBS
        self.draw_pane_border(self.left_win, "Subreddits", is_active)

        for i in range(h - 2):
            sub_idx = self.sub_scroll_top + i
            if sub_idx >= len(TARGET_SUBREDDITS): break
            sub_name = TARGET_SUBREDDITS[sub_idx]
            attr = self.attr["normal"]
            prefix = "  "
            if sub_idx == self.current_sub_index:
                attr = self.attr["highlight"]
                prefix = "> "
                if is_active: attr |= curses.A_REVERSE # Stronger highlight

            safe_addstr(self.left_win, i + 1, 1, f"{prefix}r/{sub_name}", attr)
        try:
            self.left_win.refresh()
        except curses.error: pass

    def draw_right_pane(self, h, w):
        self.right_win.erase()
        is_active = self.current_view == VIEW_LIST and self.active_pane == PANE_POSTS
        selected_sub = TARGET_SUBREDDITS[self.current_sub_index]
        self.draw_pane_border(self.right_win, f"r/{selected_sub}", is_active)

        current_posts = self.posts.get(selected_sub, [])
        y_pos = 1 # Start drawing posts at this line

        if not current_posts:
            msg = "(Press Enter in left pane to load)"
            attr = self.attr["normal"]
            if selected_sub in self.last_fetch_time:
                msg = "(No posts found or error)"
                attr = self.attr["error"]
            safe_addstr(self.right_win, y_pos, 2, msg, attr)
        else:
            for i in range(h - 2): # Iterate through available lines
                post_idx = self.post_scroll_top + i
                if post_idx >= len(current_posts) or y_pos >= h - 1: break # Check y_pos bounds

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
                    post_type_attr = self.attr["link"] if post.is_self is False else self.attr["textpost"]
                    post_type_indicator = "[L]" if post.is_self is False else "[T]"

                    # Line 1: Title
                    title_line = f"{prefix}{title}"
                    safe_addstr(self.right_win, y_pos, 1, title_line, attr)

                    # Line 2: Metadata + Type Indicator
                    meta_line = f"  {score:>4}pts {comments:>3}c {author:<15} {time_str}"
                    safe_addstr(self.right_win, y_pos + 1, 1, meta_line, self.attr["meta"])
                    indicator_x = w - len(post_type_indicator) - 2
                    safe_addstr(self.right_win, y_pos + 1, indicator_x, post_type_indicator, post_type_attr)

                    y_pos += 2 # Move down 2 lines for the next post

                except Exception:
                     safe_addstr(self.right_win, y_pos, 1, f"{prefix}[Error displaying post info]", self.attr["error"])
                     y_pos += 1 # Move down 1 line on error

        try:
            self.right_win.refresh()
        except curses.error: pass


    def draw_post_view(self, h, w):
        self.post_view_win.erase()
        self.draw_pane_border(self.post_view_win, "Post View", True) # Always active when shown

        selected_sub = TARGET_SUBREDDITS[self.current_sub_index]
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
                 # Split into lines first, then wrap each line
                 for paragraph in content_to_display.split('\n'):
                     lines.extend(textwrap.wrap(paragraph, width=w - 4, replace_whitespace=False, drop_whitespace=False))

            content_h = h - 5 # Height available for content body
            for i in range(content_h):
                line_idx = self.post_content_scroll_top + i
                if line_idx >= len(lines): break
                safe_addstr(self.post_view_win, i + 4, 2, lines[line_idx])

            # Scroll indicator
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
        self.comment_view_win.erase()
        selected_sub = TARGET_SUBREDDITS[self.current_sub_index]
        post = self.posts.get(selected_sub, [])[self.current_post_index] # Assumes post exists
        self.draw_pane_border(self.comment_view_win, f"Comments: {post.title[:w-20]}", True)

        current_comments = self.comments.get(post.id, [])
        y_pos = 1

        if not current_comments:
             msg = "(Loading comments...)" if post.id not in self.last_fetch_time else "(No comments found or error)"
             safe_addstr(self.comment_view_win, y_pos, 2, msg, self.attr["normal"] if post.id not in self.last_fetch_time else self.attr["error"])
        else:
             # Cache wrapped lines per comment to avoid re-wrapping constantly
             if not hasattr(self, '_comment_lines_cache') or self._comment_lines_cache['post_id'] != post.id:
                 self._comment_lines_cache = {'post_id': post.id, 'lines': []}
                 flat_list = [] # Build a list of (comment_obj, line_text, line_index_in_comment)
                 for c_idx, comment in enumerate(current_comments):
                      if isinstance(comment, praw.models.MoreComments):
                          line_text = f"{'  ' * comment.depth}>>> Load More Comments ({comment.count}) <<<"
                          flat_list.append({'obj': comment, 'line': line_text, 'idx': 0, 'c_idx': c_idx})
                          continue # Skip wrapping for MoreComments placeholder

                      try:
                            indent = "  " * comment.depth
                            author = f"u/{comment.author.name}" if comment.author else "[deleted]"
                            meta = f"{indent}{author} | {comment.score}pts | {format_timestamp(comment.created_utc)}"
                            body = comment.body if comment.body else ""

                            # Wrap body, respecting existing newlines
                            wrapped_body_lines = []
                            for paragraph in body.split('\n'):
                                wrapped_body_lines.extend(textwrap.wrap(indent + paragraph, width=w - 4,
                                                                         replace_whitespace=False, drop_whitespace=False,
                                                                         initial_indent=indent, subsequent_indent=indent))

                            # Add meta line first, then body lines
                            flat_list.append({'obj': comment, 'line': meta, 'idx': 0, 'c_idx': c_idx})
                            for l_idx, line in enumerate(wrapped_body_lines):
                                flat_list.append({'obj': comment, 'line': line, 'idx': l_idx + 1, 'c_idx': c_idx})
                      except Exception:
                            flat_list.append({'obj': comment, 'line': f"{indent}[Error displaying comment]", 'idx': 0, 'c_idx': c_idx})

                 self._comment_lines_cache['lines'] = flat_list

             # Draw visible lines from the cached flat list
             flat_comment_lines = self._comment_lines_cache['lines']
             for i in range(h - 2): # Available lines
                 line_idx = self.comment_scroll_top + i
                 if line_idx >= len(flat_comment_lines): break

                 line_info = flat_comment_lines[line_idx]
                 comment_obj = line_info['obj']
                 line_text = line_info['line']
                 line_in_comment_idx = line_info['idx']
                 original_comment_idx = line_info['c_idx'] # Index in the self.comments[post.id] list

                 attr = self.attr["comment"] # Default comment text color
                 prefix = ""
                 is_selected_comment = (original_comment_idx == self.current_comment_index)

                 if isinstance(comment_obj, praw.models.MoreComments):
                      attr = self.attr["meta"] # Style 'Load More' differently
                 elif line_in_comment_idx == 0: # Meta line
                      attr = self.attr["comment_meta"]
                      # Add depth indicator color (cycling)
                      depth_color_idx = comment_obj.depth % len(self.attr["comment_depth"])
                      depth_attr = self.attr["comment_depth"][depth_color_idx]
                      safe_addstr(self.comment_view_win, y_pos + i, 1, '|', depth_attr) # Draw depth marker

                 # Highlight the entire comment block if selected
                 if is_selected_comment:
                     attr = self.attr["highlight"] # Highlight background

                 # Draw the line text itself
                 safe_addstr(self.comment_view_win, y_pos + i, 2, line_text, attr)

             # Scroll indicator for comments
             if len(flat_comment_lines) > h - 2:
                 scroll_perc = int(100 * (self.comment_scroll_top + min(h - 2, len(flat_comment_lines)-self.comment_scroll_top)) / len(flat_comment_lines)) if len(flat_comment_lines) > 0 else 0
                 indicator = f"[{scroll_perc}%]"
                 safe_addstr(self.comment_view_win, h - 1, w - len(indicator) - 2, indicator)

        try:
            self.comment_view_win.refresh()
        except curses.error: pass

    def draw_ui(self):
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
            # Still draw left pane dimmly for context
            self.draw_left_pane(content_h, left_w)
            self.draw_post_view(content_h, right_w)
        elif self.current_view == VIEW_COMMENTS:
            # Still draw left pane dimmly
            self.draw_left_pane(content_h, left_w)
            self.draw_comments_view(content_h, right_w)


    def handle_resize(self):
        content_h, max_h, max_w, left_w, right_w, status_h = self.get_layout()
        curses.resizeterm(max_h, max_w)
        self.create_windows(content_h, max_w, left_w, right_w, status_h)
        # Clear potential cached wrapped lines on resize
        if hasattr(self, '_comment_lines_cache'): del self._comment_lines_cache
        self.draw_ui()


    def authenticate(self):
        global reddit_instance, CLIENT_ID, CLIENT_SECRET, USERNAME, PASSWORD
        try:
            if not CLIENT_ID: CLIENT_ID = input("Enter Reddit Client ID: ")
            if not CLIENT_SECRET: CLIENT_SECRET = input("Enter Reddit Client Secret: ")
            if not USERNAME: USERNAME = input("Enter Reddit Username: ")
            if not PASSWORD: PASSWORD = getpass.getpass("Enter Reddit Password: ")

            print("Authenticating with Reddit...")
            self.reddit = praw.Reddit(
                client_id=CLIENT_ID.strip(),
                client_secret=CLIENT_SECRET.strip(),
                user_agent=USER_AGENT.strip(),
                username=USERNAME.strip(),
                password=PASSWORD.strip(),
                check_for_async=False
            )
            user_me = self.reddit.user.me()
            if user_me is None: raise Exception("Authentication failed, user is None.")
            print(f"Authentication successful as u/{user_me.name}")
            self.set_status(f"u/{user_me.name} | Select subreddit and press Enter")
            return True
        except Exception as e:
            print(f"\n[ERROR] Reddit Authentication Failed: {e}")
            self.set_status(f"Authentication Failed: {e}")
            time.sleep(3)
            return False

    def fetch_posts(self, sub_name):
        if not self.reddit: self.set_status("Error: Not authenticated.", True); return
        self.set_status(f"Fetching posts for r/{sub_name}...")
        self.draw_ui() # Show status immediately

        try:
            subreddit = self.reddit.subreddit(sub_name)
            fetched_posts = list(subreddit.new(limit=POST_LIMIT))
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

    def fetch_comments(self, post):
        if not self.reddit: self.set_status("Error: Not authenticated.", True); return
        if post.id in self.comments: # Already fetched or fetching
            # Maybe add a check for fetch time here to allow refresh
            self.set_status(f"Displaying cached comments for {post.id}")
            return

        self.set_status(f"Fetching comments for {post.id}...")
        self.comments[post.id] = [] # Placeholder to indicate loading
        self.draw_ui() # Show status

        try:
            # Accessing post.comments performs the fetch
            post.comments.replace_more(limit=0) # Fetch top-level comments, don't automatically fetch "load more" yet
            fetched_comments = post.comments.list()
            self.comments[post.id] = fetched_comments
            self.last_fetch_time[post.id] = time.time() # Mark fetch time
             # Clear cached wrapped lines as comments are new/updated
            if hasattr(self, '_comment_lines_cache'): del self._comment_lines_cache
            self.set_status(f"Loaded {len(fetched_comments)} top-level comment items.")
            self.current_comment_index = 0
            self.comment_scroll_top = 0
        except praw.exceptions.PRAWException as e:
             self.comments[post.id] = [] # Clear on error
             self.set_status(f"Error fetching comments: {e}", True)
        except Exception as e:
             self.comments[post.id] = []
             self.set_status(f"Unexpected error fetching comments: {e}", True)


    def open_link_in_browser(self, url):
         try:
             webbrowser.open(url)
             self.set_status(f"Opened link: {url}", True)
         except Exception as e:
             self.set_status(f"Failed to open link: {e}", True)

    # --- Input Handling ---

    def _handle_list_input(self, key):
        sub_name = TARGET_SUBREDDITS[self.current_sub_index]
        current_posts = self.posts.get(sub_name, [])
        lh, lw = self.left_win.getmaxyx() # Left height/width
        rh, rw = self.right_win.getmaxyx() # Right height/width
        num_subs = len(TARGET_SUBREDDITS)
        num_posts = len(current_posts)
        lines_per_post_entry = 2 # As drawn in draw_right_pane

        if key == ord('q'): return False # Signal to quit
        elif key == ord('\t'): # Tab key
            self.active_pane = 1 - self.active_pane
            self.set_status(f"Switched to {'Posts' if self.active_pane else 'Subreddits'} pane.")
        elif key == curses.KEY_DOWN or key == ord('j'):
            if self.active_pane == PANE_SUBS:
                if self.current_sub_index < num_subs - 1:
                    self.current_sub_index += 1
                    if self.current_sub_index >= self.sub_scroll_top + lh - 2: self.sub_scroll_top += 1
            else: # PANE_POSTS
                if num_posts > 0 and self.current_post_index < num_posts - 1:
                    self.current_post_index += 1
                    visible_posts_area_h = rh - 2
                    if (self.current_post_index * lines_per_post_entry) >= (self.post_scroll_top * lines_per_post_entry + visible_posts_area_h):
                         self.post_scroll_top += 1
        elif key == curses.KEY_UP or key == ord('k'):
            if self.active_pane == PANE_SUBS:
                if self.current_sub_index > 0:
                    self.current_sub_index -= 1
                    if self.current_sub_index < self.sub_scroll_top: self.sub_scroll_top -= 1
            else: # PANE_POSTS
                 if num_posts > 0 and self.current_post_index > 0:
                    self.current_post_index -= 1
                    if (self.current_post_index * lines_per_post_entry) < (self.post_scroll_top * lines_per_post_entry):
                        self.post_scroll_top -= 1
        elif key == curses.KEY_NPAGE: # Page Down
            if self.active_pane == PANE_SUBS:
                 scroll_amount = max(1, lh - 3)
                 self.current_sub_index = min(num_subs - 1, self.current_sub_index + scroll_amount)
                 self.sub_scroll_top = min(max(0, num_subs - (lh-2)), self.sub_scroll_top + scroll_amount)
            else: # PANE_POSTS
                 scroll_amount = max(1, (rh - 3) // lines_per_post_entry)
                 self.current_post_index = min(num_posts - 1, self.current_post_index + scroll_amount)
                 self.post_scroll_top = min(max(0, num_posts - ((rh-2)//lines_per_post_entry)), self.post_scroll_top + scroll_amount)
        elif key == curses.KEY_PPAGE: # Page Up
             if self.active_pane == PANE_SUBS:
                 scroll_amount = max(1, lh - 3)
                 self.current_sub_index = max(0, self.current_sub_index - scroll_amount)
                 self.sub_scroll_top = max(0, self.sub_scroll_top - scroll_amount)
             else: # PANE_POSTS
                 scroll_amount = max(1, (rh - 3) // lines_per_post_entry)
                 self.current_post_index = max(0, self.current_post_index - scroll_amount)
                 self.post_scroll_top = max(0, self.post_scroll_top - scroll_amount)
        elif key == curses.KEY_HOME:
             if self.active_pane == PANE_SUBS:
                 self.current_sub_index = 0; self.sub_scroll_top = 0
             else: # PANE_POSTS
                 self.current_post_index = 0; self.post_scroll_top = 0
        elif key == curses.KEY_END:
            if self.active_pane == PANE_SUBS:
                 self.current_sub_index = num_subs - 1
                 self.sub_scroll_top = max(0, num_subs - (lh - 2))
            else: # PANE_POSTS
                 if num_posts > 0:
                     self.current_post_index = num_posts - 1
                     self.post_scroll_top = max(0, num_posts - ((rh - 2) // lines_per_post_entry))
        elif key == ord('\n') or key == curses.KEY_ENTER:
            if self.active_pane == PANE_SUBS:
                self.fetch_posts(sub_name)
                self.active_pane = PANE_POSTS # Switch focus after loading
            else: # Enter on post -> switch to post content view
                 if num_posts > 0:
                    self.current_view = VIEW_POST
                    self.post_content_scroll_top = 0
                    self.set_status(f"Viewing post: {current_posts[self.current_post_index].title[:50]}...")
        elif key == ord('c'): # View Comments
             if self.active_pane == PANE_POSTS and num_posts > 0:
                 post = current_posts[self.current_post_index]
                 self.current_view = VIEW_COMMENTS
                 self.fetch_comments(post) # Fetch if needed
                 self.set_status(f"Loading comments for: {post.title[:50]}...")
             else:
                 self.set_status("Focus post list (Tab) and select post first", True)
        elif key == ord('o'): # Open Link
             if self.active_pane == PANE_POSTS and num_posts > 0:
                 post = current_posts[self.current_post_index]
                 self.open_link_in_browser(post.url)
             else:
                 self.set_status("Focus post list (Tab) and select post first", True)
        elif key == ord('r'): # Refresh current subreddit
            self.fetch_posts(sub_name)
            self.active_pane = PANE_POSTS

        return True # Keep running

    def _handle_post_view_input(self, key):
        ph, pw = self.post_view_win.getmaxyx()
        content_h = ph - 5
        sub_name = TARGET_SUBREDDITS[self.current_sub_index]
        post = self.posts.get(sub_name, [])[self.current_post_index]
        content_to_display = post.selftext if post.is_self else f"Link: {post.url}"
        lines = []
        if content_to_display:
            for paragraph in content_to_display.split('\n'):
                 lines.extend(textwrap.wrap(paragraph, width=pw - 4, replace_whitespace=False, drop_whitespace=False))
        num_lines = len(lines)

        if key == ord('q') or key == 27: # Quit or Escape
            self.current_view = VIEW_LIST
            self.set_status(f"Back to post list in r/{sub_name}")
        elif key == curses.KEY_DOWN or key == ord('j'):
            if self.post_content_scroll_top < num_lines - content_h: self.post_content_scroll_top += 1
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
        elif key == ord('o'): # Open link (even if self-text post, open its permalink)
             self.open_link_in_browser(post.permalink if post.is_self else post.url)

        return True # Keep running


    def _handle_comments_view_input(self, key):
        # Calculation for comment scrolling needs the cached flat list
        if not hasattr(self, '_comment_lines_cache'): return True # Don't handle input if no comments drawn

        ch, cw = self.comment_view_win.getmaxyx()
        content_h = ch - 2
        flat_comment_lines = self._comment_lines_cache['lines']
        num_lines = len(flat_comment_lines)
        sub_name = TARGET_SUBREDDITS[self.current_sub_index]
        post = self.posts.get(sub_name, [])[self.current_post_index] # Assumes post exists

        if key == ord('q') or key == 27: # Quit or Escape
            self.current_view = VIEW_LIST
            self.set_status(f"Back to post list in r/{sub_name}")
        elif key == curses.KEY_DOWN or key == ord('j'):
            # Scroll visible lines first
            if self.comment_scroll_top < num_lines - content_h:
                 self.comment_scroll_top += 1
            # TODO: Add logic to move current_comment_index down to next comment block? More complex.
        elif key == curses.KEY_UP or key == ord('k'):
             if self.comment_scroll_top > 0:
                 self.comment_scroll_top -= 1
            # TODO: Add logic to move current_comment_index up?
        elif key == curses.KEY_NPAGE:
            scroll_amount = max(1, content_h - 1)
            self.comment_scroll_top = min(max(0, num_lines - content_h), self.comment_scroll_top + scroll_amount)
        elif key == curses.KEY_PPAGE:
            scroll_amount = max(1, content_h - 1)
            self.comment_scroll_top = max(0, self.comment_scroll_top - scroll_amount)
        elif key == curses.KEY_HOME:
             self.comment_scroll_top = 0
             self.current_comment_index = 0 # Go to first comment
        elif key == curses.KEY_END:
             self.comment_scroll_top = max(0, num_lines - content_h)
             # Find last comment index:
             if flat_comment_lines: self.current_comment_index = flat_comment_lines[-1]['c_idx']

        elif key == ord('o'): # Open link of the *original post* when viewing comments
             self.open_link_in_browser(post.url)
             # TODO: Add ability to open links *within* comments? Much harder.

        # Note: Selecting/collapsing/replying to comments is not implemented
        return True

    def run(self):
        if not self.authenticate(): return
        try:
            curses.wrapper(self._run_curses)
        except Exception as e:
            curses.endwin() # Ensure terminal is reset
            print(f"\nAn unexpected error occurred in the main loop: {e}")
            import traceback
            traceback.print_exc()

    def _run_curses(self, stdscr):
        self.stdscr = stdscr
        self.setup_curses()
        content_h, max_h, max_w, left_w, right_w, status_h = self.get_layout()
        self.create_windows(content_h, max_w, left_w, right_w, status_h)

        running = True
        while running:
            self.draw_ui()
            key = self.stdscr.getch()

            if key == curses.KEY_RESIZE:
                self.handle_resize()
                continue

            if self.current_view == VIEW_LIST:
                running = self._handle_list_input(key)
            elif self.current_view == VIEW_POST:
                running = self._handle_post_view_input(key)
            elif self.current_view == VIEW_COMMENTS:
                running = self._handle_comments_view_input(key)

# --- Run the app ---
if __name__ == "__main__":
    if os.name == 'nt':
        try: import windows_curses
        except ImportError: print("Please install 'windows-curses'"); sys.exit(1)

    app = RedditCursesApp(None)
    app.run()
