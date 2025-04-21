# 🎮 curses: Browse Reddit like a Terminal Pro

[![click_to_see_screen_shot!]](red01.jpg)

Tired of endless scrolling, distracting sidebars, and resource-hogging browser tabs just to check Reddit? **CursesReddit TUI** strips it all away, giving you a pure, fast, keyboard-first Reddit experience right in your terminal.

Think `newsboat` but for Reddit. It's lightweight, built with Python and `curses`, and designed for folks who love their terminal.

## ✨ Features

*   **Subreddit Hopping:** Browse your fave subs (you define the list!).
*   **Post Glancer:** Quickly view the latest posts (titles, score, author, time).
*   **Link vs. Text:** See instantly if it's a link `[L]` or text `[T]` post.
*   **Distraction-Free Reading:** View post selftext or link URLs without leaving the terminal.
*   **Comment Diving:** Read comment threads with basic indentation and depth colors.
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

## 👎 The Real Talk (Cons / Limitations)

*   **Read-Only Zone:** This is for browsing, chief. You **cannot** vote, comment, post, send messages, check your inbox, etc.
*   **Text Is King:** No images, videos, or fancy embeds are displayed directly in the terminal. You'll need to use the 'Open Link' (`o`) feature for media.
*   **API Key Needed:** You gotta set up your own Reddit API key (it's free, but an extra step). See Setup below.
*   **API Limits Apply:** You're using the free Reddit API tier. If you go *absolutely nuts* refreshing constantly, you *might* hit a rate limit (but it's pretty generous for normal browsing).
*   **Basicville:** No multi-account support, advanced search/filtering, comment collapsing/replying, or saved posts. It's simple on purpose.
*   **Blocking IO:** Fetching posts/comments is currently blocking, meaning the UI might freeze for a brief moment on slow connections. Patience, young padawan.
*   **Terminal Funks:** `curses` can sometimes look slightly different or have minor glitches depending on your terminal emulator or OS (especially Windows).

## 🔧 Requirements

*   **Python 3.x** (Should be 3.7+ ideally)
*   **A Reddit Account** (duh)
*   **Reddit API Credentials** (See Setup!)
*   **Python Libraries:**
    *   `praw` (The Python Reddit API Wrapper)
    *   `windows-curses` (ONLY if you're on Windows)

## 🛠️ Setup - Get Ready to Rock

1.  **Clone or Download:**
    ```bash
    git clone https://your-repo-url-here/curses-reddit-tui.git
    cd curses-reddit-tui
    ```
    (Or just download the `reddit_curses_v2.py` script)

2.  **Install Python Stuff:**
    ```bash
    pip install praw
    ```
    **If you are on Windows:**
    ```bash
    pip install windows-curses
    ```
    (Linux/macOS usually have `curses` built-in).

3.  **Get Reddit API Keys (The "Hard" Part - Not Really):**
    *   Go to your Reddit App Preferences: [https://www.reddit.com/prefs/apps](https://www.reddit.com/prefs/apps)
    *   Scroll down and click "**are you a developer? create an app...**".
    *   Fill it out:
        *   **Name:** `MyCursesClient` (or whatever you want)
        *   Select **`script`** as the app type.
        *   **Description:** (optional) `Terminal client`
        *   **About URL:** (optional) leave blank
        *   **Redirect URI:** `http://localhost:8080` (important for script apps, even if we don't use it directly here)
    *   Click "**create app**".
    *   You'll see your app listed. **Carefully copy:**
        *   The **Client ID** (it's under the app name, looks like `aBcDeFgHiJkLmN1`)
        *   The **Client Secret** (labeled "secret")
    *   **Keep these secret! Don't share them.**

4.  **Configure the Script (Optional but Recommended):**
    *   Open the Python script (`reddit_curses_v2.py` or whatever you called it).
    *   Near the top, find the **Configuration** section.
    *   **IMPORTANT:** Change `USER_AGENT` to include your Reddit username! Like: `USER_AGENT = "CursesRedditClient/0.2 by YourUsername"`
    *   Edit `TARGET_SUBREDDITS` to list the subreddits you want quick access to.
    *   Adjust `POST_LIMIT` and `COMMENT_LIMIT` if you want.
    *   *Optionally*, you *can* hardcode your `CLIENT_ID`, `CLIENT_SECRET`, `USERNAME`, and `PASSWORD` here, but it's generally **safer** to let the script prompt you each time.

5.  **Run It!**
    ```bash
    python reddit_curses_v2.py
    ```
    *   It will prompt you for your Client ID, Client Secret, Reddit Username, and Reddit Password (password typing is hidden) if you didn't hardcode them.

## ⌨️ How to Use It (Keybindings)

Navigate using the keyboard. Think `vim` or `less`.

**General:**
*   `q` : Quit the application (in List View)

**List View (Subreddits / Posts):**
*   `Up / k` : Move selection up
*   `Down / j` : Move selection down
*   `PgUp` : Scroll list up a page
*   `PgDn` : Scroll list down a page
*   `Home` : Jump to top of list
*   `End` : Jump to bottom of list
*   `Tab` : Switch focus between Subreddit pane (left) and Post pane (right)
*   `Enter`:
    *   On Subreddit (left pane): Load posts & focus Post pane
    *   On Post (right pane): Switch to Post View
*   `c` : (When a post is selected) Switch to Comments View for that post
*   `o` : (When a post is selected) Open post URL in your web browser
*   `r` : Refresh posts for the currently selected subreddit

**Post View (Reading Selftext/Link):**
*   `Up / k` : Scroll content up
*   `Down / j` : Scroll content down
*   `PgUp` : Scroll content up a page
*   `PgDn` : Scroll content down a page
*   `Home` : Jump to top of content
*   `End` : Jump to bottom of content
*   `o` : Open post's URL (link post) or Permalink (text post) in browser
*   `q / Esc` : Go back to List View

**Comments View:**
*   `Up / k` : Scroll comments up
*   `Down / j` : Scroll comments down
*   `PgUp` : Scroll comments up a page
*   `PgDn` : Scroll comments down a page
*   `Home` : Jump to top comment
*   `End` : Jump to bottom comment
*   `o` : Open the *original post's* URL in browser
*   `q / Esc` : Go back to List View

## 🤝 Contributing

Hey, feel free to fork this, fix bugs, add features (maybe async fetching?), or make it look even cooler.

*   Open an Issue to report bugs or suggest features.
*   Submit Pull Requests for improvements. Keep it lean and focused!

## 📜 License

[Choose a License - MIT Recommended]

---

*Happy terminal browsing!* 😎
