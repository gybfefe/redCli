# 🎮 CursesReddit TUI v0.3: Browse Reddit like a Terminal Pro 🚀

[![click here for demo]](red01.jpg)

Tired of endless scrolling, distracting sidebars, and resource-hogging browser tabs just to check Reddit? **CursesReddit TUI** strips it all away, giving you a pure, fast, keyboard-first Reddit experience right in your terminal.

Think `newsboat` but for Reddit. It's lightweight, built with Python and `curses`, configured via a simple `config.ini`, and designed for terminal lovers.

## ✨ What's New in v0.3

*   **Config File:** No more hardcoding secrets! Credentials, user agent, and subreddits are now stored in `config.ini`. (Safer for sharing!)
*   **Load More Comments:** Hit `l` on a "Load More" item in the comments view to fetch the replies.
*   **Better Loading:** Panes now show a clear "Loading..." message during data fetches.
*   **Stickied Indicator:** Stickied posts are marked with `[S]`.
*   **Comment Selection:** The *entire* selected comment block is highlighted for clarity.

## ✨ Core Features

*   **Configurable Subreddit Hopping:** Browse your fave subs (defined in `config.ini`).
*   **Post Glancer:** Quickly view the latest posts (titles, score, author, time, stickied).
*   **Link vs. Text:** See instantly if it's a link `[L]` or text `[T]` post.
*   **Distraction-Free Reading:** View post selftext or link URLs without leaving the terminal.
*   **Comment Diving:** Read comment threads with indentation, depth colors, and load more functionality.
*   **Browser Escape Hatch:** Quickly open post links or comment permalinks in your default browser (`o` key!).
*   **Keyboard Is King:** Navigate everything with keys (Vim/`less`/`newsboat` style).
*   **Lightweight AF:** Uses minimal resources thanks to `curses`. Runs smooth even on a potato. 🥔
*   **Looks Legit:** That sweet, sweet terminal aesthetic.

## 👍 The Good Stuff (Pros)

*   **Seriously Fast:** `curses` leaves web browsers in the dust. Low RAM and CPU usage.
*   **Zero Distractions:** No ads, no suggested posts, no flashy avatars. Just the content you want. Pure focus mode.
*   **Keyboard Wizardry:** Navigate Reddit at the speed of thought (or typing). Perfect for keyboard addicts.
*   **Terminal Native:** Fits perfectly into your `tmux` or `screen` workflow. Impress your friends.
*   **Bandwidth Friendly:** Fetches primarily text via the API. Great for crappy Wi-Fi or mobile hotspots.
*   **Configurable:** Easily change subreddits and settings in `config.ini`.
*   **Safer:** Credentials stored externally, not directly in the script.

## 👎 The Real Talk (Cons / Limitations)

*   **Read-Only Zone:** Still for browsing. You **cannot** vote, comment, post, send messages, check your inbox, etc.
*   **Text Is King:** No images, videos, or fancy embeds are displayed directly in the terminal. Use 'Open Link' (`o`).
*   **API Key Needed:** You *still* gotta set up your own Reddit API key (see Setup).
*   **API Limits Apply:** You're using the free Reddit API tier. Normal browsing is fine, but excessive refreshing *could* hit limits.
*   **Basicville:** No multi-account support, advanced search/filtering, comment collapsing/replying, or saved posts. Simple on purpose.
*   **Blocking IO:** Fetching posts/comments *still* blocks the UI briefly on slow connections. Patience needed.
*   **Terminal Funks:** `curses` looks/acts slightly differently depending on your terminal/OS.
*   **'Load More' is Basic:** Loading more comments replaces the placeholder; fine-grained loading isn't implemented.

## 🔧 Requirements

*   **Python 3.x** (3.7+ recommended)
*   **A Reddit Account**
*   **Reddit API Credentials** (See Setup!)
*   **Python Libraries:**
    *   `praw`
    *   `windows-curses` (ONLY if you're on Windows)

## 🛠️ Setup - Get Ready to Rock

1.  **Clone or Download:**
    ```bash
    git clone https://your-repo-url-here/curses-reddit-tui.git
    cd curses-reddit-tui
    ```
    (Or download the `.py` script)

2.  **Install Python Stuff:**
    ```bash
    pip install praw
    ```
    **If you are on Windows:**
    ```bash
    pip install windows-curses
    ```

3.  **Get Reddit API Keys:**
    *   *(If you did this before, you can reuse your keys!)*
    *   Go to: [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
    *   Click "**are you a developer? create an app...**".
    *   **Name:** `MyCursesClient` (or similar)
    *   Select **`script`** app type.
    *   **Redirect URI:** `http://localhost:8080`
    *   Click "**create app**".
    *   Copy your **Client ID** (under app name) and **Client Secret**.

4.  **Create `config.ini`:**
    *   The script will *automatically create a default `config.ini`* the first time you run it if it doesn't exist, and then exit.
    *   **Open the generated `config.ini` file.**
    *   **Fill in the `[Credentials]` section:**
        *   `ClientID = YOUR_CLIENT_ID_HERE`
        *   `ClientSecret = YOUR_CLIENT_SECRET_HERE`
        *   `Username = YOUR_REDDIT_USERNAME`
        *   `Password = YOUR_REDDIT_PASSWORD`
        *   `UserAgent = CursesRedditClient/0.3 by YOUR_REDDIT_USERNAME` (Customize this!)
    *   **Customize the `[Settings]` section:**
        *   `Subreddits = commandline, linux, python` (Change to your preferred subs, comma-separated)
        *   Adjust `PostLimit` or `CommentLimit` if desired.
    *   **Save the file.**

5.  **IMPORTANT (If using Git): Add `config.ini` to your `.gitignore` file!** You do NOT want to accidentally commit your secret credentials. Create a file named `.gitignore` in the same directory if it doesn't exist, and add this line:
    ```
    config.ini
    ```

6.  **Run It!**
    ```bash
    python reddit_curses_v3.py
    ```
    *   It should now read your `config.ini` and authenticate directly. If there's an issue with the config, it *might* fall back to prompting you.

## ⌨️ How to Use It (Keybindings)

**General:**
*   `q` : Quit the application (in List View)

**List View (Subreddits / Posts):**
*   `Up / k` : Move selection up
*   `Down / j` : Move selection down
*   `PgUp` / `PgDn` : Scroll list page up/down
*   `Home` / `End` : Jump to top/bottom of list
*   `Tab` : Switch focus between Subreddit pane (left) and Post pane (right)
*   `Enter`:
    *   On Subreddit: Load posts & focus Post pane
    *   On Post: Switch to Post View
*   `c` : (When post selected) Switch to Comments View
*   `o` : (When post selected) Open post URL in web browser
*   `r` : Refresh posts for the current subreddit

**Post View (Reading Selftext/Link):**
*   `Arrows/jk/PgUp/PgDn/Home/End`: Scroll content
*   `o` : Open post's URL/Permalink in browser
*   `q / Esc` : Go back to List View

**Comments View:**
*   `Up / k` : Select previous comment object
*   `Down / j` : Select next comment object
*   `PgUp` / `PgDn` : Scroll visible comment lines page up/down
*   `Home` / `End` : Jump to top/bottom comment & scroll view
*   `l` : (When "Load More" selected) Attempt to load more replies
*   `o` : Open the *original post's* Permalink in browser
*   `q / Esc` : Go back to List View

## 🤝 Contributing

Fork it, fix it, feature it!

*   Open an Issue for bugs/suggestions.
*   Submit Pull Requests. Ideas: Async fetching, comment collapsing, better error handling...


*Keep calm and terminal on!* 😎
