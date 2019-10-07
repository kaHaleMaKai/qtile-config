-- Standard awesome library
local gears = require("gears")
local awful = require("awful")
require("awful.autofocus")
require("awful.spawn")
require("awful.widget")
-- Widget and layout library
local wibox = require("wibox")
-- Theme handling library
local beautiful = require("beautiful")
-- Notification library
local naughty = require("naughty")
local menubar = require("menubar")
local hotkeys_popup = require("awful.hotkeys_popup").widget
--require("awful.hotkeys_popup.keys.vim")
local volume_control = require("modules/volume-control")
local revelation = require("revelation")
revelation.font = "Hack 20"
local math = require("math")
local fns = require("modules/fns")
local logger = require("modules/log")
local logging = require("logging")
logger.logger:setLevel(logging.DEBUG)
--local batteryarc_widget = require("modules/awesome-wm-widgets.batteryarc-widget.batteryarc")
local cpu_widget = require("modules/awesome-wm-widgets.cpu-widget.cpu-widget")
local ram_widget = require("modules/awesome-wm-widgets.ram-widget.ram-widget")
--local email_widget = require("modules/awesome-wm-widgets.email-widget.email")
--local volumebar_widget = require("modules/awesome-wm-widgets.volumebar-widget.volumebar")
--local brightness_widget = require("modules/awesome-wm-widgets.brightness-widget.brightness")
local assault = require('modules/assault.awesomewm.assault')
local net_widgets = require('modules/net_widgets')
local ps_widget = require('modules/ps-widget')
local net_widget = require('modules/net-widget')
local run_shell = require("modules/awesome-wm-widgets.run-shell.run-shell")
local capslock_widget = require("modules/capslock")
local calendar = require("modules/calendar")

local capslocker = capslock_widget({})

local myassault = assault({
   critical_level = 0.15,
   critical_color = "#ff0000",
   charging_color = "#8090c0",
   normal_color = "#8090c0",
   width = 16,
   height = 8,
})

local net_wireless = net_widgets.wireless()
local net_wired = net_widgets.indicator()
opacity_on_unfocus = 0
local with_margin = function(widget, left, right)
    return {
        widget,
        layout = wibox.container.margin({
            widget = widget,
            left = left,
            right = right,
            top = 0,
            bottom = 0,
            opacity = 0,
        })
    }
end

-- {{{ Error handling
-- Check if awesome encountered an error during startup and fell back to
-- another config (This code will only ever execute for the fallback config)
if awesome.startup_errors then
    naughty.notify({ preset = naughty.config.presets.critical,
                     title = "Oops, there were errors during startup!",
                     text = awesome.startup_errors })
end

-- Handle runtime errors after startup
do
    local in_error = false
    awesome.connect_signal("debug::error", function (err)
        -- Make sure we don't go into an endless error loop
        if in_error then return end
        in_error = true

        naughty.notify({ preset = naughty.config.presets.critical,
                         title = "Oops, an error happened!",
                         text = tostring(err) })
        in_error = false
    end)
end
-- }}}

-- {{{ Variable definitions
-- Themes define colours, icons, font and wallpapers.
config_path = awful.util.getdir("config")
icon_path = config_path .. "/icons"
theme_path = config_path .. "/themes/my-theme"
beautiful.init(theme_path .. "/theme.lua")
revelation.init()

-- This is used later as the default terminal and editor to run.
--terminal = "/home/lars/.cargo/bin/alacritty"
terminal = "xfce4-terminal"
editor = os.getenv("EDITOR") or "vi"
screensaver = '/usr/bin/cinnamon-screensaver'
screensaver_cmd = string.format('%s-command --lock', screensaver)
editor_cmd = terminal .. " -e " .. editor

-- Default modkey.
-- Usually, Mod4 is the key with a logo between Control and Alt.
-- If you do not like this or do not have such a key,
-- I suggest you to remap Mod4 to another key using xmodmap or other tools.
-- However, you can use another modifier like Mod1, but it may interact with others.

modkey = "Mod4"
altkey = "Alt"

-- Table of layouts to cover with awful.layout.inc, order matters.
awful.layout.layouts = {
    awful.layout.suit.tile,
    awful.layout.suit.tile.left,
    awful.layout.suit.tile.bottom,
    awful.layout.suit.tile.top,
    awful.layout.suit.fair,
    awful.layout.suit.fair.horizontal,
    awful.layout.suit.spiral,
    awful.layout.suit.spiral.dwindle,
    awful.layout.suit.max,
    awful.layout.suit.max.fullscreen,
    awful.layout.suit.magnifier,
    awful.layout.suit.floating
}
-- }}}

-- {{{ custom modules
volumecfg = volume_control({ notification_theme = "HighContrast" })
-- }}}

-- {{{ Menu
-- Create a launcher widget and a main menu
myawesomemenu = {
   { "hotkeys", function() return false, hotkeys_popup.show_help end},
   { "manual", terminal .. " -e man awesome" },
   { "edit config", editor_cmd .. " " .. awesome.conffile },
   { "restart", awesome.restart },
   { "quit", function() awesome.quit() end}
}

mymainmenu = awful.menu({ items = { { "awesome", myawesomemenu, beautiful.awesome_icon },
                                    { "open terminal", terminal }
                                  }
                        })

mylauncher = awful.widget.launcher({ image = beautiful.awesome_icon,
                                     menu = mymainmenu })

-- Menubar configuration
menubar.utils.terminal = terminal -- Set the terminal for applications that require it
-- }}}

-- Keyboard map indicator and switcher
mykeyboardlayout = awful.widget.keyboardlayout()

-- {{{ Wibar
-- Create a textclock widget
mytextclock = wibox.widget.textclock()
calendar({}):attach(mytextclock)

local function with_modkey_mapping(new_modkey, keys)
end

-- Create a wibox for each screen and add it
local taglist_buttons = awful.util.table.join(
                    awful.button({ }, 1, function(t) t:view_only() end),
                    awful.button({ modkey }, 1, function(t)
                                              if client.focus then
                                                  client.focus:move_to_tag(t)
                                              end
                                          end),
                    awful.button({ }, 3, awful.tag.viewtoggle),
                    awful.button({ modkey }, 3, function(t)
                                              if client.focus then
                                                  client.focus:toggle_tag(t)
                                              end
                                          end),
                    awful.button({ }, 4, function(t) awful.tag.viewnext(t.screen) end),
                    awful.button({ }, 5, function(t) awful.tag.viewprev(t.screen) end)
                )

local tasklist_buttons = awful.util.table.join(
                     awful.button({ }, 1, function (c)
                                              if c == client.focus then
                                                  c.minimized = true
                                              else
                                                  -- Without this, the following
                                                  -- :isvisible() makes no sense
                                                  c.minimized = false
                                                  if not c:isvisible() and c.first_tag then
                                                      c.first_tag:view_only()
                                                  end
                                                  -- This will also un-minimize
                                                  -- the client, if needed
                                                  client.focus = c
                                                  c:raise()
                                              end
                                          end),
                     awful.button({ }, 3, fns.client_menu_toggle_fn()),
                     awful.button({ }, 4, function ()
                                              awful.client.focus.byidx(1)
                                          end),
                     awful.button({ }, 5, function ()
                                              awful.client.focus.byidx(-1)
                                          end))

local function set_wallpaper(s)
    -- Wallpaper
    if beautiful.wallpaper then
        local wallpaper = beautiful.wallpaper
        -- If wallpaper is a function, call it with the screen
        if type(wallpaper) == "function" then
            wallpaper = wallpaper(s)
        end
        gears.wallpaper.maximized(wallpaper, s, true)
    end
end

local function set_external_screen(size)
    local cmd = string.format("set-screen-layout %s", size)
    awful.spawn.with_shell(cmd)
    awesome.restart()
    if size == "dual" or "dual-external" then
        awful.screen.focus(1)
        awful.tag.incmwfact(0.05 * 6)
    end
end

--screen.connect_signal("added", function (s)
  --set_external_screen("dual-external")
--end)

--screen.connect_signal("removed", function (s)
    --naughty.notify({ preset = naughty.config.presets.critical,
                     --title = "screen removed",
                     --text = string.format("idx:%d,cnt:%d,geo:%dx%d",s.index,screen.count(),s.geometry.width,s.geometry.height) })

    ----if screen.count == 1 then
        ----local width = s.geometry.width
        ----local height = s.geometry.height
        ----if width == 1366 and height == 768 then
            ----set_external_screen("small")
        ----elseif width == 2560 and height == 1440 then
            ----set_external_screen("large")
        ----else
        ----end
    ----end
--end)

-- Re-set wallpaper when a screen's geometry changes (e.g. different resolution)

local tagtables = {
    {
        {
            tags = { "1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f" },
            layouts = awful.layout.layouts[1]
        },
    },
    {
        {
            tags = { "1", "2", "3", "4", "5", "6", "7", "8", "9" },
            layouts = awful.layout.layouts[1]
        },
        {
            tags = { "a", "b", "c", "d", "e", "f" },
            layouts = { awful.layout.suit.tile.left, awful.layout.suit.max.fullscreen }
        }
    },
    {
        {
            tags = { "1", "2", "3", "4", "5", "6", "7", "8", "9" },
            layouts = awful.layout.layouts[1]
        },
        {
            tags = { "b", "c" },
            layouts = { awful.layout.suit.tile.left, awful.layout.suit.max.fullscreen }
        },
        {
            tags = { "a", "b", "e", "f" },
            layouts = { awful.layout.suit.tile.left, awful.layout.suit.max.fullscreen }
        }
    }
}
local app_placement = {
    {
        spotify = { tag = "b" },
        zim = { tag = "b" },
        chat = { tag = "c" },
        heidi = { tag = "d" },
        evolution = { tag = "e" },
        firefox = { tag = "f" },
    },
    {
        spotify = { tag = "e" },
        zim = { tag = "c" },
        chat = { tag = "c" },
        heidi = { tag = "d" },
        evolution = { tag = "e" },
        firefox = { tag = "f" },
    },
    {
        spotify = { tag = "e" },
        zim = { tag = "c" },
        chat = { tag = "c" },
        heidi = { tag = "d" },
        evolution = { tag = "e" },
        firefox = { tag = "f" },
    }
}
local function with_app_placement(name, table)
    local placement = app_placement[screen.count()]
    local result = fns.merge(app_placement[screen.count()][name], table)
    if not result.screen then
        result.screen = screen.count()
    end
    logger.logger:debug(result)
    return result
end

awful.screen.connect_for_each_screen(function(s)
    local screen_index = s.index
    local num_screens = screen.count()

    set_wallpaper(s)

    -- Each screen has its own tag table.
    local tagtable = tagtables[num_screens][screen_index].tags
    local layout_table = tagtables[num_screens][screen_index].layouts
    awful.tag(tagtable, s, layout_table)

    -- Create a promptbox for each screen
    s.mypromptbox = require("prompt")()
    --s.mypromptbox = awful.widget.prompt()
    -- Create an imagebox widget which will contains an icon indicating which layout we're using.
    -- We need one layoutbox per screen.
    s.mylayoutbox = awful.widget.layoutbox(s)
    s.mylayoutbox:buttons(awful.util.table.join(
                           awful.button({ }, 1, function () awful.layout.inc( 1) end),
                           awful.button({ }, 3, function () awful.layout.inc(-1) end),
                           awful.button({ }, 4, function () awful.layout.inc( 1) end),
                           awful.button({ }, 5, function () awful.layout.inc(-1) end)))
    -- Create a taglist widget
    s.mytaglist = awful.widget.taglist(s, awful.widget.taglist.filter.all, taglist_buttons)

   -- Create a tasklist widget
    s.mytasklist = awful.widget.tasklist(s, awful.widget.tasklist.filter.currenttags, tasklist_buttons)

    -- Create the wibox
    s.mywibox = awful.wibar({ position = "top", screen = s })

    local systray = wibox.widget.systray()
    systray.opacity = 0.5

    -- Add widgets to the wibox
    s.mywibox:setup {
        layout = wibox.layout.align.horizontal,
        { -- Left widgets
            layout = wibox.layout.fixed.horizontal,
            mylauncher,
            s.mytaglist,
            s.mypromptbox,
        },
        s.mytasklist, -- Middle widget
        { -- Right widgets
            layout = wibox.layout.fixed.horizontal,
            capslocker.widget,
            systray,
            ram_widget,
            cpu_widget,
            ps_widget,
            net_widget,
            --with_margin(volumecfg.widget, 0, 4),
            volumecfg.widget,
            myassault,
            mytextclock,
            s.mylayoutbox,
        },
    }

end)
-- }}}

-- {{{ Mouse bindings
root.buttons(awful.util.table.join(
    --awful.button({ }, 3, function () mymainmenu:toggle() end),
    awful.button({ }, 4, fns.view_next),
    awful.button({ }, 5, fns.view_tag)
))
-- }}}

local function print_current_tag()
    local tag_name = awful.screen.focused().selected_tag.name
    naughty.notify({
        preset = naughty.config.presets.normal,
        timeout = 2,
        position = "top_left",
        text = string.format("%s", tag_name),
        margin = 10,
        height = 150,
        width = 150,
        opacity = 1,
        font = "Hack 96px"
    })
end

-- {{{ Key bindings
globalkeys = awful.util.table.join(
    awful.key({ modkey,   "Shift" }, "t",      print_current_tag,
              {description="show current tag", group="awesome"}),
    ),

    -- Layout manipulation
    awful.key({ modkey, "Shift"   }, "j", function () awful.client.swap.byidx(-1)    end,
              {description = "swap with next client by index", group = "client"}),
    awful.key({ modkey, "Shift"   }, "k", function () awful.client.swap.byidx(1)    end,
              {description = "swap with previous client by index", group = "client"}),
    awful.key({ modkey, "Control"}, "Right", function () awful.screen.focus_relative(1) end,
              {description = "focus the next screen", group = "screen"}),
    awful.key({ modkey, "Control"}, "Left", function () awful.screen.focus_relative(-1) end,
              {description = "focus the previous screen", group = "screen"}),
    awful.key({ modkey,           }, "u", awful.client.urgent.jumpto,
              {description = "jump to urgent client", group = "client"}),

    awful.key({ modkey,
                "Control" },
              "l",
              function ()
                --awful.spawn.with_shell("i3lock-fancy -g -- scrot -q 100 -m -z")
                --awful.spawn.with_shell("cinnamon-screensaver-command -l")
                awful.spawn.with_shell(screensaver_cmd)
              end),
    awful.key({ modkey,
                "Shift" },
              "s",
              function ()
                awful.spawn.with_shell("deepin-screenshot")
              end),
    awful.key({ modkey,           }, "Tab",
        function ()
            awful.client.focus.history.previous()
            if client.focus then
                client.focus:raise()
            end
        end,
        {description = "go back", group = "client"}),

    -- Standard program
    awful.key({ modkey,           }, "Return", function () awful.spawn(terminal) end,
              {description = "open a terminal", group = "launcher"}),
    awful.key({ modkey, "Shift"   }, "Return",
                function ()
                    awful.spawn(terminal, { floating = true, placement = awful.placement.centered, width = 800, height = 500 })
                end,
              {description = "open a terminal", group = "launcher"}),
    awful.key({ modkey, "Control"   }, "t",
                function ()
                    awful.spawn("xfce4-terminal --title=taskwarrior --dynamic-title-mode=none --zoom=1 -e '/home/lars/bin/_open-task-and-zsh'",
                                { floating = true, class = "taskwarrior", modal = true, sticky = true, placement = awful.placement.centered, width = 1000, height = 500 })
                end,
              {description = "open a terminal", group = "launcher"}),
    awful.key({ modkey, "Control" }, "Return", fns.spawn_in_fg("vim"),
              {description = "open vim", group = "launcher"}),
    awful.key({ modkey, "Control", "Shift" }, "Return",
                function ()
                    awful.spawn(editor_cmd, { floating = true, placement = awful.placement.centered, width = 800, height = 500 })
                end,
              {description = "open vim", group = "launcher"}),

    awful.key({ modkey, "Control" }, "r", awesome.restart,
              {description = "reload awesome", group = "awesome"}),
    awful.key({ modkey, "Shift", "Control"   }, "q", awesome.quit,
              {description = "quit awesome", group = "awesome"}),

    awful.key({ modkey,           }, "l",     function () awful.tag.incmwfact( 0.05)          end,
              {description = "increase master width factor", group = "layout"}),
    awful.key({ modkey,           }, "h",     function () awful.tag.incmwfact(-0.05)          end,
              {description = "decrease master width factor", group = "layout"}),
    awful.key({ modkey, "Shift"   }, "h",     function () awful.tag.incnmaster( 1, nil, true) end,
              {description = "increase the number of master clients", group = "layout"}),
    awful.key({ modkey, "Shift"   }, "l",     function () awful.tag.incnmaster(-1, nil, true) end,
              {description = "decrease the number of master clients", group = "layout"}),
    awful.key({ modkey, "Control" }, "h",     function () awful.tag.incncol( 1, nil, true)    end,
              {description = "increase the number of columns", group = "layout"}),
    awful.key({ modkey, "Control" }, "l",     function () awful.tag.incncol(-1, nil, true)    end,
              {description = "decrease the number of columns", group = "layout"}),
    awful.key({ modkey,           }, "space", function () awful.layout.inc( 1)                end,
              {description = "select next", group = "layout"}),
    awful.key({ modkey, "Shift"   }, "space", function () awful.layout.inc(-1)                end,
              {description = "select previous", group = "layout"}),

    awful.key({ modkey, "Control" }, "n",
              function ()
                  local c = awful.client.restore()
                  -- Focus restored client
                  if c then
                      client.focus = c
                      c:raise()
                  end
              end,
              {description = "restore minimized", group = "client"}),

    -- Prompt
    awful.key({ modkey }, "r", function ()
        --awful.screen.focused().mypromptbox:run()
        run_shell.launch()
    end, {description = "run prompt", group = "launcher"}),

    awful.key({ modkey }, "x",
              function ()
                  awful.prompt.run {
                    prompt       = "Run Lua code: ",
                    textbox      = awful.screen.focused().mypromptbox.widget,
                    exe_callback = awful.util.eval,
                    history_path = awful.util.get_cache_dir() .. "/history_eval"
                  }
              end,
              {description = "lua execute prompt", group = "awesome"}),
    awful.key({}, "XF86AudioMute", function() volumecfg:pactl_toggle() end),
    awful.key({}, "XF86AudioRaiseVolume", function() volumecfg:up() end),
    awful.key({}, "XF86AudioLowerVolume", function() volumecfg:down() end),
    awful.key({}, "XF86AudioPlay",        function() awful.spawn.with_shell("spotifycli --playpause") end),
    awful.key({}, "XF86AudioNext",        function() awful.spawn.with_shell("spotifycli --next") end),
    awful.key({}, "XF86AudioPrev",        function() awful.spawn.with_shell("spotifycli --prev") end),
    --awful.key({ modkey }, "z", fns.hide_wibar, {description = "toggle statusbar"}),

    awful.key({ modkey }, "F1", function (c)
        set_external_screen("small")
    end),

    awful.key({ modkey }, "F2", function (c)
        set_external_screen("dual-external")
    end),

    awful.key({ modkey }, "F3", function (c)
        set_external_screen("large")
    end)

)

clientkeys = awful.util.table.join(
    awful.key({ modkey,           }, "z",
        function (c)
            c.fullscreen = not c.fullscreen
            c:raise()
        end,
        {description = "toggle fullscreen", group = "client"}),
    awful.key({ modkey, "Shift"   }, ".",      function (c) c:kill()                         end,
              {description = "close", group = "client"}),
    awful.key({ modkey, "Control" }, "space",  awful.client.floating.toggle                     ,
              {description = "toggle floating", group = "client"}),
    awful.key({ modkey, "Control" }, "Return", function (c) c:swap(awful.client.getmaster()) end,
              {description = "move to master", group = "client"}),
    awful.key({ modkey,           }, "o",      function (c) c:move_to_screen()               end,
              {description = "move to screen", group = "client"}),
    awful.key({ modkey,           }, "t",      function (c) c.ontop = not c.ontop            end,
              {description = "toggle keep on top", group = "client"}),
    awful.key({ modkey,           }, "n",
        function (c)
            -- The client currently has the input focus, so it cannot be
            -- minimized, since minimized clients can't have the focus.
            c.minimized = true
        end ,
        {description = "minimize", group = "client"}),
    awful.key({ modkey,           }, "m",
        function (c)
            c.maximized = not c.maximized
            c:raise()
        end ,
        {description = "maximize", group = "client"})
        --,
     --awful.key({ modkey, "Shift"   }, "h",
       --function (c)
           --local curidx = awful.tag.getidx()
           --if curidx == 1 then
               --awful.client.movetotag(tags[client.focus.screen][9])
           --else
               --awful.client.movetotag(tags[client.focus.screen][curidx - 1])
           --end
       --end),
     --awful.key({ modkey, "Shift"   }, "l",
       --function (c)
           --local curidx = awful.tag.getidx()
           --if curidx == 9 then
               --awful.client.movetotag(tags[client.focus.screen][1])
           --else
               --awful.client.movetotag(tags[client.focus.screen][curidx + 1])
           --end
       --end)
)

-- Bind all key numbers to tags.
-- Be careful: we use keycodes to make it works on any keyboard layout.
-- This should map on the top row of your keyboard, usually 1 to 9.
local tag_names = {"1", "2", "3", "4", "5", "6", "7", "8", "9", "a", "b", "c", "d", "e", "f"}

for i = 1, 15 do
    globalkeys = awful.util.table.join(globalkeys,
        -- View tag only.
        awful.key({ modkey }, tag_names[i],
            function ()
                local tag_name = tag_names[i]
                fns.view_tag(tag_name)
            end,
            {description = "view tag #"..i, group = "tag"}),
        -- Toggle tag display.
        awful.key({ modkey, "Control" }, tag_names[i],
            function ()
                local screen = awful.screen.focused()
                local tag = screen.tags[i]
                if tag then
                    awful.tag.viewtoggle(tag)
                end
            end,
            {description = "toggle tag #" .. i, group = "tag"}),
        -- Move client to tag.
        awful.key({ modkey, "Shift" }, tag_names[i],
            function ()
                local current_screen = awful.screen.focused()
                local current_tag = current_screen.selected_tag
                if client.focus then
                    local tag = fns.get_tag(tag_names[i])
                    if tag then
                        client.focus:move_to_screen(tag.screen)
                        client.focus:move_to_tag(tag)
                    end
                end
                awful.screen.focus(current_screen.index)
                current_tag:view_only()
            end,
            {description = "move focused client to tag #"..i, group = "tag"}),
        -- Toggle tag on focused client.
        awful.key({ modkey, "Control", "Shift" }, tag_names[i],
            function ()
                if client.focus then
                    local tag = client.focus.screen.tags[i]
                    if tag then
                        client.focus:toggle_tag(tag)
                    end
                end
            end,
            {description = "toggle focused client on tag #" .. i, group = "tag"})
    )
end

clientbuttons = awful.util.table.join(
    awful.button({ }, 1, function (c) client.focus = c; c:raise() end),
    awful.button({ modkey }, 1, awful.mouse.client.move),
    awful.button({ modkey }, 3, awful.mouse.client.resize))

-- Set keys
root.keys(globalkeys)
-- }}}

-- {{{ Rules
-- Rules to apply to new clients (through the "manage" signal).

clientbuttons_jetbrains = gears.table.join(
    awful.button({ modkey }, 1, awful.mouse.client.move),
    awful.button({ modkey }, 3, awful.mouse.client.resize)
)

awful.rules.rules = {
    -- All clients will match this rule.
    { rule = { },
      properties = { border_width = beautiful.border_width,
                     border_color = beautiful.border_normal,
                     focus = awful.client.focus.filter,
                     raise = true,
                     keys = clientkeys,
                     buttons = clientbuttons,
                     screen = awful.screen.preferred,
                     placement = awful.placement.no_overlap+awful.placement.no_offscreen,
                     size_hints_honor = true
     }
    },

    -- Floating clients.
    { rule_any = {
        instance = {
          "DTA",  -- Firefox addon DownThemAll.
          "copyq",  -- Includes session name in class.
        },
        class = {
          "Arandr",
          "Gpick",
          "Kruler",
          "MessageWin",  -- kalarm.
          "Sxiv",
          "Wpa_gui",
          "pinentry",
          "veromix",
          "MPlayer",
          "pinentry",
          "Gimp",
          "Shutter",
          "xtightvncviewer"},

        name = {
          "Event Tester",  -- xev.
        },
        role = {
          "AlarmWindow",  -- Thunderbird's calendar.
          "pop-up",       -- e.g. Google Chrome's (detached) Developer Tools.
        }
      }, properties = { floating = true }},


    { rule_any = {
        class = {
            "Evolution",
            "Gajim",
            "jetbrains-idea-ce",
            "jetbrains-pycharm-ce",
            "DBeaver",
            "Spotify",
            "Code",
        },
    }, properties = { opacity = 0.97 } },

    { rule_any = { class = { "Zim" } },
      properties = with_app_placement("zim", {opacity = 0.95}) },
    { rule_any = { class = { "Spotify" } },
      properties = with_app_placement("spotify", {opacity = 0.95}) },
    { rule = { class = "Firefox", role = "chat"},
      properties = with_app_placement("chat", { }) },
    { rule = { class = "Firefox", role = "browser"},
      properties = with_app_placement("firefox", { }) },
    { rule = { class = "Evolution" },
      properties = with_app_placement("evolution", {opacity = 0.93}) },
    { rule = { class = "Evolution", role = "EMailBrowser-%d*"},
      properties = { floating = true, height = 500, above = true } },
    { rule_any = {
        class = { "Xfce4-terminal", "Alacritty", "kitty", "awesome/rc.lua" }
      }, properties = { opacity = 0.92 } },
    { rule = { class = "Wine", name = ".*HeidiSQL.*" },
      properties = with_app_placement("heidi", { maximized_horizontally = true, maximized_vertically = true, opacity = 0.95 }) },

}

-- }}}

-- {{{ Signals
-- Signal function to execute when a new client appears.
client.connect_signal("manage", function (c)
    -- Set the windows at the slave,
    -- i.e. put it at the end of others instead of setting it master.
    -- if not awesome.startup then awful.client.setslave(c) end

    if awesome.startup and
      not c.size_hints.user_position
      and not c.size_hints.program_position then
        -- Prevent clients from being unreachable after screen count changes.
        awful.placement.no_offscreen(c)
    end
end)

-- Add a titlebar if titlebars_enabled is set to true in the rules.
client.connect_signal("request::titlebars", function(c)
    -- buttons for the titlebar
    local buttons = awful.util.table.join(
        awful.button({ }, 1, function()
            client.focus = c
            c:raise()
            awful.mouse.client.move(c)
        end),
        awful.button({ }, 3, function()
            client.focus = c
            c:raise()
            awful.mouse.client.resize(c)
        end)
    )

    awful.titlebar(c) : setup {
        { -- Left
            awful.titlebar.widget.iconwidget(c),
            buttons = buttons,
            layout  = wibox.layout.fixed.horizontal
        },
        { -- Middle
            { -- Title
                align  = "center",
                widget = awful.titlebar.widget.titlewidget(c)
            },
            buttons = buttons,
            layout  = wibox.layout.flex.horizontal
        },
        { -- Right
            awful.titlebar.widget.floatingbutton (c),
            awful.titlebar.widget.maximizedbutton(c),
            awful.titlebar.widget.stickybutton   (c),
            awful.titlebar.widget.ontopbutton    (c),
            awful.titlebar.widget.closebutton    (c),
            layout = wibox.layout.fixed.horizontal()
        },
        layout = wibox.layout.align.horizontal
    }
end)

-- Enable sloppy focus, so that focus follows mouse.
client.connect_signal("mouse::enter", function(c)
    if awful.layout.get(c.screen) ~= awful.layout.suit.magnifier
        and awful.client.focus.filter(c) then
        client.focus = c
    end
end)
-- Enable sloppy focus, so that focus follows mouse. Keep focus on Java dialogs.
--client.connect_signal("mouse::enter", function(c)
	--local focused = client.focus
	---- Is the new window the same application as the currently
	---- focused one? (by comparing X window classes)
	---- Are we currently focusing a Java Frame, Window or Dialog
	---- and want to switch focus inside that group?
	--local isJavaInstance = function(instance)
		--return string.match(instance, "^sun-awt-X11-X")
	--end
	--if focused and focused.class == c.class
		--and isJavaInstance(focused.instance)
		--and isJavaInstance(c.instance) then
		--return
	--end
	--if awful.layout.get(c.screen) ~= awful.layout.suit.magnifier
		--and awful.client.focus.filter(c) then
		--client.focus = c
	--end
--end)
client.connect_signal("focus", function(c)
    if c._original_opacity then
        c.opacity = c._original_opacity
    end
    c.border_color = beautiful.border_focus
end)
client.connect_signal("unfocus", function(c)
    if c._original_opacity == nil then
        c._original_opacity = c.opacity
    end
    c.opacity = c.opacity - opacity_on_unfocus
    c.border_color = beautiful.border_normal
end)

-- }}}

-- autostarts
local autostart = {
    "setxkbmap de deadacute",
    "unclutter -root",
    "xcompmgr",
    "xfce4-power-manager",
    screensaver,
    string.format("xss-lock -l -v -- %s", screensaver_cmd),
--    "nm-applet",
    "volti",
    --"blueman-applet",
    "shiftred load-config",
}

for i = 1, #autostart do
    fns.run_once(autostart[i])
end

--awful.spawn.with_shell("pactl unload-module module-bluetooth-discover && pactl load-module module-bluetooth-discover ")
awful.spawn.with_shell("xdotool search --name 'whatsapp|mattermost' set_window --role chat")
awful.screen.focus(1)
--fns.run_once("blueman-applet", nil, nil, nil)

-- vim: ft=lua
