-- GalleryDance: loop dances on the gallery heroine, picked from an in-game panel (F7), with speed control.
-- Dances are cooked AnimSequences in Paks\~mods\GalleryDance_P.pak, listed in ..\dances.txt (written by the build).
-- How it plays them: the gallery anim BP (<Name>GalleryAnimBlueprint_C) feeds its variable `AnimSequence` into a
-- SequencePlayer, so swapping that variable loops our clip with the game's physics and bone tweaks intact.
local function log(s) print("[GalleryDance] " .. tostring(s) .. "\n") end
local function valid(o) return o and o:IsValid() end
local function name(o) local ok, s = pcall(function() return o:GetFullName() end); return ok and s or "?" end

local MOD_DIR = debug.getinfo(1, "S").source:match("^@(.*)[/\\]Scripts[/\\]")
local SPEEDS = { 0.5, 1.0, 1.5, 2.0 }
local TOGGLE_KEY = Key.F7

---------------------------------------------------------------- dance catalog
local DANCES = {}  -- lower-case character -> { {path=, label=}, ... }
local function loadCatalog()
    local f = io.open(MOD_DIR .. "\\dances.txt", "r")
    if not f then log("dances.txt missing"); return end
    for line in f:lines() do
        local char, short = line:match("^/Game/Mods/GalleryDance/([^/]+)/A_[^_]+_Dance_(.+)$")
        if char then
            local key = char:lower()
            DANCES[key] = DANCES[key] or {}
            local label = short:gsub("(%l)(%u)", "%1 %2"):upper()  -- BellyDance -> BELLY DANCE
            table.insert(DANCES[key], { path = line, label = label })
        end
    end
    f:close()
end

local function isDance(path)
    return path and path:find("/Game/Mods/GalleryDance/", 1, true) == 1
end

---------------------------------------------------------------- assets
local helpers
local function load(p)
    local full = p .. "." .. p:match("([^/]+)$")
    local a = StaticFindObject(full)
    if valid(a) then return a end
    pcall(LoadAsset, p); a = StaticFindObject(full)
    if valid(a) then return a end
    -- mod-pak assets aren't in the game's asset registry: FAssetData::GetAsset loads straight from the path
    helpers = valid(helpers) and helpers or StaticFindObject("/Script/AssetRegistry.Default__AssetRegistryHelpers")
    if valid(helpers) then
        local ok, r = pcall(function() return helpers:GetAsset({ ObjectPath = FName(full, EFindName.FNAME_Add) }) end)
        if ok and valid(r) then return r end
    end
    return nil
end
local function isSeq(a) return valid(a) and a:GetClass():GetFName():ToString() == "AnimSequence" end
local function pathOf(o) return name(o):match("^AnimSequence (/[^%.]+)") end  -- keep paths, never swapped-out objects (GC)

---------------------------------------------------------------- the gallery heroine
local function heroine()
    for _, c in ipairs(FindAllOf("SkeletalMeshComponent") or {}) do
        if valid(c) then
            local ai = c:GetAnimInstance()
            if valid(ai) and ai:GetClass():GetFName():ToString():find("GalleryAnimBlueprint", 1, true)
               and c.AnimationMode == 0 then
                local okr, seen = pcall(function() return c:GetOwner():WasRecentlyRendered(0.5) end)
                if not okr or seen then return c, ai end
            end
        end
    end
end
local function charOf(c)
    local m = name(c.SkeletalMesh)
    return m:match("/Characters/([^/]+)/") or "?"
end

-- per heroine (by component address): menu pose to return to, and what we're playing
local state = {}
local speed = 1.0

local function physPath(o) return name(o):match("^PhysicsAsset (/[^%.]+)") end
local REINIT_TICKS = 1  -- polls (150 ms each): let the new clip pose the bones first, then rebuild the bodies there
local tick = 0

local function play(c, ai, path)
    local a = load(path)
    if not isSeq(a) then log("could not load " .. path); return end
    local st = state[c:GetAddress()]
    ai.AnimSequence = a
    pcall(function() c.GlobalAnimRateScale = speed end)
    st.playing = path
    -- dances use the heroine's base physics asset (the menu poses each have their own tuned one)
    local okb, base = pcall(function() return c:GetOwner().PhysicsAsset end)
    st.phys = okb and physPath(base) or st.menuPhys
    st.reinitAt = tick + REINIT_TICKS
end

local function stop(c, ai)
    local st = state[c:GetAddress()]
    if st.menu then
        local a = load(st.menu)
        if isSeq(a) then ai.AnimSequence = a end
    end
    pcall(function() c.GlobalAnimRateScale = 1.0 end)
    st.playing = nil
    st.phys = st.menuPhys
    st.reinitAt = tick + REINIT_TICKS
end

local function reinitPhysics(c, st)
    st.reinitAt = nil
    local pa = st.phys and StaticFindObject(st.phys .. "." .. st.phys:match("([^/]+)$"))
    if not valid(pa) and st.phys then pcall(LoadAsset, st.phys); pa = StaticFindObject(st.phys .. "." .. st.phys:match("([^/]+)$")) end
    local ok1 = valid(pa) and pcall(function() c:SetPhysicsAsset(pa, true) end)
    local ok2 = pcall(function() c:ResetAnimInstanceDynamics(2) end)  -- ETeleportType::ResetPhysics
    if not ok1 and not ok2 then log("physics reset unavailable") end
end

---------------------------------------------------------------- panel (same widget trick as BodySlider)
-- A throwaway SliderOption_C instance hosts our own CanvasPanel as its WidgetTree root; buttons are toggle
-- CheckBoxes. Each poll compares a button's checked state with what it should show: a mismatch is a click.
local HOST_CLASS = "/Game/Core/UI/Settings/SliderOption.SliderOption_C"
local TEX_WHITE = "/Game/ArtAssets/Shared/Interface/Textures/UI_BlankWhite_BC"
local BOX    = { R = 0.06, G = 0.02, B = 0.13, A = 0.96 }
local FRAME  = { R = 0.55, G = 0.20, B = 0.85, A = 1.0 }
local ACCENT = { R = 1.0,  G = 0.22, B = 0.80, A = 1.0 }
local LILAC  = { R = 0.86, G = 0.78, B = 1.0,  A = 1.0 }
local SHADOW = { R = 0.10, G = 0.0,  B = 0.20, A = 0.9 }
local WHITE  = { R = 1.0,  G = 1.0,  B = 1.0,  A = 1.0 }
local BTN    = { R = 0.30, G = 0.14, B = 0.52, A = 1.0 }
local BTN_H  = { R = 0.45, G = 0.22, B = 0.75, A = 1.0 }
local BW, PAD, ROW = 420, 24, 42

local panelOn = false
local ui = {}

local function try(fn) pcall(fn) end
local function setText(tb, s) if valid(tb) then tb:SetText(FText(s)) end end
local function construct(clsPath, outer) return StaticConstructObject(StaticFindObject(clsPath), outer) end
local function texture(path)
    local n = path:match("([^/]+)$")
    local t = StaticFindObject(path .. "." .. n)
    if not valid(t) then pcall(LoadAsset, path); t = StaticFindObject(path .. "." .. n) end
    return valid(t) and t or nil
end
local function place(canvas, child, x, y, w, h)
    canvas:AddChild(child):SetOffsets({ Left = x, Top = y, Right = w, Bottom = h })
end
local function rect(tree, canvas, tex, col, x, y, w, h)
    local img = construct("/Script/UMG.Image", tree)
    if tex then img:SetBrushFromTexture(tex, false) end
    img:SetColorAndOpacity(col)
    place(canvas, img, x, y, w, h)
end
local function label(tree, canvas, font, size, col, x, y, w, h)
    local tb = construct("/Script/UMG.TextBlock", tree)
    try(function() tb.Font = font; tb.Font.Size = size end)
    try(function()
        tb:SetColorAndOpacity({ SpecifiedColor = col, ColorUseRule = 0 })
        tb:SetShadowColorAndOpacity(SHADOW); tb:SetShadowOffset({ X = 2, Y = 2 })
    end)
    place(canvas, tb, x, y, w, h)
    return tb
end
local function button(tree, canvas, white, font, text, x, y, w, h)
    local cb = construct("/Script/UMG.CheckBox", tree)
    local st = cb.WidgetStyle
    st.CheckBoxType = 1  -- ToggleButton
    local function br(b, col) b.ResourceObject = white; b.DrawAs = 3; b.TintColor = { SpecifiedColor = col, ColorUseRule = 0 } end
    br(st.UncheckedImage, BTN); br(st.UncheckedHoveredImage, BTN_H); br(st.UncheckedPressedImage, ACCENT)
    br(st.CheckedImage, ACCENT); br(st.CheckedHoveredImage, ACCENT); br(st.CheckedPressedImage, ACCENT)
    st.Padding = { Left = 0, Top = 0, Right = 0, Bottom = 0 }
    local tb = construct("/Script/UMG.TextBlock", tree)
    try(function() tb.Font = font; tb.Font.Size = 14 end)
    try(function() tb:SetColorAndOpacity({ SpecifiedColor = WHITE, ColorUseRule = 0 }); tb:SetJustification(1) end)
    setText(tb, text)
    local slot = cb:AddChild(tb)
    try(function() slot:SetHorizontalAlignment(2); slot:SetVerticalAlignment(2) end)
    place(canvas, cb, x, y, w, h)
    return cb
end

local function destroyUI()
    if valid(ui.host) then pcall(function() ui.host:RemoveFromParent() end) end
    ui = {}
end

local function buildUI(char, list)
    local cls = StaticFindObject(HOST_CLASS)
    if not valid(cls) then pcall(LoadAsset, "/Game/Core/UI/Settings/SliderOption"); cls = StaticFindObject(HOST_CLASS) end
    local pc = FindFirstOf("PlayerController")
    local lib = StaticFindObject("/Script/UMG.Default__WidgetBlueprintLibrary")
    local layout = StaticFindObject("/Script/UMG.Default__WidgetLayoutLibrary")
    if not (valid(cls) and valid(pc) and valid(lib) and valid(layout)) then return false end
    local vp, scale = layout:GetViewportSize(pc), layout:GetViewportScale(pc)
    local W, H = vp.X / scale, vp.Y / scale

    local n = math.max(#list, 1)
    local BH = 74 + n * ROW + 12 + 26 + 34 + 20 + 34 + PAD   -- title, dance rows, speed label + row, footer, bottom padding
    local x0, y0 = math.floor(W - BW - W * 0.04), math.floor((H - BH) / 2)

    local host = lib:Create(pc, cls, pc)
    if not valid(host) then return false end
    local font = host.TextBlock_Description.Font
    local tree = host.WidgetTree
    local canvas = construct("/Script/UMG.CanvasPanel", tree)
    tree.RootWidget = canvas
    local white = texture(TEX_WHITE)

    rect(tree, canvas, white, FRAME,  x0 - 2, y0 - 2, BW + 4, BH + 4)
    rect(tree, canvas, white, BOX,    x0, y0, BW, BH)
    rect(tree, canvas, white, ACCENT, x0, y0, BW, 4)
    rect(tree, canvas, white, FRAME,  x0 + PAD, y0 + 62, BW - 2 * PAD, 1)
    ui.title = label(tree, canvas, font, 24, ACCENT, x0 + PAD, y0 + 16, BW - 2 * PAD, 34)
    setText(ui.title, "DANCE  |  " .. char:upper())

    ui.dances = {}
    local y = y0 + 74
    if #list == 0 then
        setText(label(tree, canvas, font, 15, LILAC, x0 + PAD, y + 8, BW - 2 * PAD, 24), "No dances for this heroine yet")
    end
    for i, d in ipairs(list) do
        ui.dances[i] = { cb = button(tree, canvas, white, font, d.label, x0 + PAD, y + (i - 1) * ROW, BW - 2 * PAD, ROW - 8), path = d.path }
    end
    y = y + n * ROW + 12
    setText(label(tree, canvas, font, 13, LILAC, x0 + PAD, y, 120, 20), "SPEED")
    y = y + 26
    ui.speeds = {}
    local sw = math.floor((BW - 2 * PAD - 3 * 8) / 4)
    for i, s in ipairs(SPEEDS) do
        ui.speeds[i] = { cb = button(tree, canvas, white, font, string.format("%gx", s), x0 + PAD + (i - 1) * (sw + 8), y, sw, 34), v = s }
    end
    y = y + 34 + 20
    ui.stop  = button(tree, canvas, white, font, "STOP",  x0 + PAD, y, 120, 34)
    ui.close = button(tree, canvas, white, font, "CLOSE", x0 + BW - PAD - 120, y, 120, 34)

    host:AddToViewport(50)
    ui.host, ui.char = host, char
    return true
end

local function poll()
    tick = tick + 1
    local c, ai = heroine()
    if not c then
        if valid(ui.host) then ui.host:SetVisibility(1) end
        return
    end
    local key = c:GetAddress()
    local st = state[key] or {}
    state[key] = st

    -- follow the game: whatever non-dance pose the menu sets becomes the "stop" target;
    -- if the menu changes the pose while we dance, the dance is over
    local cur = pathOf(ai.AnimSequence)
    if st.reinitAt and tick >= st.reinitAt then reinitPhysics(c, st) end
    if cur and not isDance(cur) then
        st.menu = cur
        st.menuPhys = physPath(c.PhysicsAssetOverride) or st.menuPhys
        if st.playing then st.playing = nil; pcall(function() c.GlobalAnimRateScale = 1.0 end) end
    end

    local char = charOf(c)
    local list = DANCES[char:lower()] or {}
    if not panelOn then
        if valid(ui.host) then ui.host:SetVisibility(1) end
        return
    end
    if not (valid(ui.host) and ui.host:IsInViewport() and ui.char == char) then
        destroyUI()
        if not buildUI(char, list) then return end
    end
    ui.host:SetVisibility(0)

    -- A click flips a toggle away from the state we last showed. Find clicks against that old state first,
    -- then act once (acting inside the loop made the still-lit buttons read as clicks too).
    if ui.close:IsChecked() then ui.close:SetIsChecked(false); panelOn = false; ui.host:SetVisibility(1); return end
    local stopClick = ui.stop:IsChecked()
    local newSpeed
    for _, s in ipairs(ui.speeds) do
        if s.cb:IsChecked() ~= (speed == s.v) and s.v ~= speed then newSpeed = s.v end
    end
    local pick, unpick
    for _, d in ipairs(ui.dances) do
        if d.cb:IsChecked() ~= (st.playing == d.path) then
            if d.path == st.playing then unpick = true else pick = d.path end
        end
    end
    ui.stop:SetIsChecked(false)
    if newSpeed then
        speed = newSpeed
        if st.playing then pcall(function() c.GlobalAnimRateScale = speed end) end
    end
    if stopClick or (unpick and not pick) then
        if st.playing then stop(c, ai) end
    elseif pick then
        play(c, ai, pick)
    end
    -- show the current state
    for _, s in ipairs(ui.speeds) do s.cb:SetIsChecked(speed == s.v) end
    for _, d in ipairs(ui.dances) do d.cb:SetIsChecked(st.playing == d.path) end
end

RegisterKeyBind(TOGGLE_KEY, function() panelOn = not panelOn end)

local lastErr
LoopInGameThreadWithDelay(150, function()
    local ok, err = pcall(poll)
    if not ok and tostring(err) ~= lastErr then lastErr = tostring(err); log("error: " .. lastErr) end
end)

loadCatalog()
