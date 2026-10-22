-- ============================================================
--  color_sort_scene.lua
--  CoppeliaSim Child Script — attached to SceneManager
--  Includes Live On-Screen Dashboard & Interactive Block Spawner
-- ============================================================

local SPAWN_INTERVAL  = 4.5      -- seconds between auto-spawns
local CONVEYOR_SPEED  = 0.14     -- m/s
local BLOCK_SIZE      = 0.05     -- cube side length (m)
local BLOCK_MASS      = 0.2      -- kg
local PICKUP_WAIT     = 6.0      -- seconds fallback to hold conveyor

local COLORS = {
    {name='red',    rgb={1.0, 0.15, 0.15}},
    {name='green',  rgb={0.15, 0.85, 0.15}},
    {name='blue',   rgb={0.15, 0.35, 1.0}},
    {name='yellow', rgb={1.0,  0.85, 0.1}},
}

local CONVEYOR_JOINT  = '/ConveyorBelt'
local PROX_SENSOR     = '/ProxSensor'
local SPAWN_POINT     = '/SpawnPoint'

local conveyorHandle  = nil
local proxHandle      = nil
local spawnHandle     = nil
local lastSpawnTime   = 0
local conveyorStopped = false
local stopTimer       = 0
local blocks          = {}
local ui              = nil
local autoSpawn       = true
local lastCountsSig   = ""

-- ── UI Callbacks (User decides which block comes!) ─────────────
function spawnRedClicked()
    spawnBlockNamed('red')
end

function spawnGreenClicked()
    spawnBlockNamed('green')
end

function spawnBlueClicked()
    spawnBlockNamed('blue')
end

function spawnYellowClicked()
    spawnBlockNamed('yellow')
end

function toggleAutoClicked()
    autoSpawn = not autoSpawn
    sim.setInt32Signal('auto_spawn', autoSpawn and 1 or 0)
    if ui then
        if autoSpawn then
            simUI.setButtonText(ui, 6, "Auto-Spawn: ON (Click to Pause)")
        else
            simUI.setButtonText(ui, 6, "Auto-Spawn: OFF (Manual Only)")
        end
    end
end
-- ──────────────────────────────────────────────────────────────

function sysCall_init()
    conveyorHandle = sim.getObject(CONVEYOR_JOINT, {noError=true})
    proxHandle     = sim.getObject(PROX_SENSOR, {noError=true})
    spawnHandle    = sim.getObject(SPAWN_POINT, {noError=true})

    -- Create In-Scene Dashboard & Control UI
    local uiXml = [[
    <ui title="Sorting Dashboard" closeable="false" resizable="false">
        <group layout="vbox" style="padding: 8px;">
            <label text="LIVE BIN SCOREBOARD" style="font-weight: bold; font-size: 13px;" />
            <label id="1" text="[RED]    Red Bin:    0 blocks" style="color: #d32f2f; font-weight: bold; font-size: 12px;" />
            <label id="2" text="[GREEN]  Green Bin:  0 blocks" style="color: #388e3c; font-weight: bold; font-size: 12px;" />
            <label id="3" text="[BLUE]   Blue Bin:   0 blocks" style="color: #1976d2; font-weight: bold; font-size: 12px;" />
            <label id="4" text="[YELLOW] Yellow Bin: 0 blocks" style="color: #f57f17; font-weight: bold; font-size: 12px;" />
            <label id="5" text="TOTAL SORTED: 0 blocks" style="font-weight: bold; font-size: 13px; margin-top: 4px;" />
            
            <label text="USER SPAWN CONTROLS" style="font-weight: bold; font-size: 13px; margin-top: 10px;" />
            <label text="Click a button to spawn that block:" style="font-size: 11px;" />
            <group layout="hbox">
                <button text="Spawn RED" on-click="spawnRedClicked" style="background-color: #ffcdd2; font-weight: bold;" />
                <button text="Spawn GREEN" on-click="spawnGreenClicked" style="background-color: #c8e6c9; font-weight: bold;" />
            </group>
            <group layout="hbox">
                <button text="Spawn BLUE" on-click="spawnBlueClicked" style="background-color: #bbdefb; font-weight: bold;" />
                <button text="Spawn YELLOW" on-click="spawnYellowClicked" style="background-color: #fff9c4; font-weight: bold;" />
            </group>
            <button id="6" text="Auto-Spawn: ON (Click to Pause)" on-click="toggleAutoClicked" style="margin-top: 6px;" />
        </group>
    </ui>
    ]]
    pcall(function()
        ui = simUI.create(uiXml)
    end)

    print('[Scene] Color Sorting Scene & Dashboard initialized.')
end

function spawnBlockNamed(colorName)
    local c = nil
    for _, col in ipairs(COLORS) do
        if col.name == colorName then
            c = col
            break
        end
    end
    if not c then
        c = COLORS[math.random(#COLORS)]
    end

    local handle = sim.createPureShape(
        0,          -- shape type: 0 = cuboid
        8+16+32,    -- options: respondable + dynamic + visible
        {BLOCK_SIZE, BLOCK_SIZE, BLOCK_SIZE},
        BLOCK_MASS,
        nil
    )

    sim.setShapeColor(handle, nil, sim.colorcomponent_ambient_diffuse, c.rgb)
    sim.setShapeColor(handle, nil, sim.colorcomponent_emission,        {0.05, 0.05, 0.05})

    local spawnPos = {-0.45, 0.5, 0.045}
    if spawnHandle and spawnHandle ~= -1 then
        spawnPos = sim.getObjectPosition(spawnHandle, sim.handle_world)
        spawnPos[3] = spawnPos[3] + BLOCK_SIZE / 2 + 0.01
    end
    sim.setObjectPosition(handle, sim.handle_world, spawnPos)
    sim.writeCustomStringData(handle, 'blockColor', c.name)
    sim.setObjectAlias(handle, 'Block_' .. c.name .. '_' .. handle)

    table.insert(blocks, handle)
    lastSpawnTime = sim.getSimulationTime()
    print('[Scene] Spawned ' .. c.name:upper() .. ' block (handle=' .. handle .. ')')
    return handle
end

function sysCall_actuation()
    local t = sim.getSimulationTime()
    local dt = sim.getSimulationTimeStep()

    -- ── Check for auto_spawn signal from Python ──────────────────────────
    local autoSig = sim.getInt32Signal('auto_spawn')
    if autoSig ~= nil then
        local wantAuto = (autoSig == 1)
        if wantAuto ~= autoSpawn then
            autoSpawn = wantAuto
            if ui then
                if autoSpawn then
                    pcall(simUI.setButtonText, ui, 6, "Auto-Spawn: ON (Click to Pause)")
                else
                    pcall(simUI.setButtonText, ui, 6, "Auto-Spawn: OFF (Manual Only)")
                end
            end
        end
    end

    -- ── Check for user spawn requests from Python ─────────────────────────
    local req = sim.getStringSignal('user_spawn_request')
    if req and #req > 0 then
        spawnBlockNamed(req)
        sim.clearStringSignal('user_spawn_request')
    end

    -- ── Update scoreboard UI from Python signal ───────────────────────────
    local countsSig = sim.getStringSignal('sorted_counts')
    if countsSig and countsSig ~= lastCountsSig then
        lastCountsSig = countsSig
        local r, g, b, y = countsSig:match("(%d+),(%d+),(%d+),(%d+)")
        if r and ui then
            r, g, b, y = tonumber(r), tonumber(g), tonumber(b), tonumber(y)
            local total = r + g + b + y
            pcall(simUI.setLabelText, ui, 1, string.format("[RED]    Red Bin:    %d blocks", r))
            pcall(simUI.setLabelText, ui, 2, string.format("[GREEN]  Green Bin:  %d blocks", g))
            pcall(simUI.setLabelText, ui, 3, string.format("[BLUE]   Blue Bin:   %d blocks", b))
            pcall(simUI.setLabelText, ui, 4, string.format("[YELLOW] Yellow Bin: %d blocks", y))
            pcall(simUI.setLabelText, ui, 5, string.format("TOTAL SORTED: %d blocks", total))
        end
    end

    -- ── Auto-Spawn blocks if enabled ──────────────────────────────────────
    if autoSpawn and not conveyorStopped and (t - lastSpawnTime) >= SPAWN_INTERVAL then
        local canSpawn = true
        for _, h in ipairs(blocks) do
            local ok, pos = pcall(sim.getObjectPosition, h, sim.handle_world)
            if ok and pos[1] < -0.25 then
                canSpawn = false
                break
            end
        end
        if canSpawn then
            spawnBlockNamed(nil) -- random color
            lastSpawnTime = t
        end
    end

    -- ── Conveyor block motion along belt to pickup zone ───────────────────
    if not conveyorStopped then
        for _, h in ipairs(blocks) do
            local ok, pos = pcall(sim.getObjectPosition, h, sim.handle_world)
            if ok then
                local parent = sim.getObjectParent(h)
                if (parent == -1 or parent == sim.handle_scene) and pos[1] < 0.0 then
                    pos[1] = math.min(0.0, pos[1] + CONVEYOR_SPEED * dt)
                    sim.setObjectPosition(h, sim.handle_world, pos)
                end
            end
        end
    end

    -- ── Proximity sensor detection ────────────────────────────────────────
    if proxHandle and proxHandle ~= -1 then
        if not conveyorStopped then
            local result, dist, point, objHandle = sim.readProximitySensor(proxHandle)
            if result == 1 then
                conveyorStopped = true
                stopTimer       = t
                print('[Scene] Block arrived at pickup zone — conveyor stopped.')
            end
        else
            local result = sim.readProximitySensor(proxHandle)
            if result == 0 and (t - stopTimer) > 1.5 then
                conveyorStopped = false
                print('[Scene] Pickup cleared — resuming conveyor.')
            elseif (t - stopTimer) >= PICKUP_WAIT then
                conveyorStopped = false
                print('[Scene] Timeout — resuming conveyor.')
            end
        end
    end

    -- ── Clean up blocks that fall below z = -2.0 ─────────────────────────
    for i = #blocks, 1, -1 do
        local h = blocks[i]
        local ok, pos = pcall(sim.getObjectPosition, h, sim.handle_world)
        if ok and pos[3] < -2.0 then
            local parent = sim.getObjectParent(h)
            if parent == -1 or parent == sim.handle_scene then
                pcall(sim.removeObject, h)
                table.remove(blocks, i)
            end
        end
    end
end

function sysCall_cleanup()
    if ui then
        pcall(simUI.destroy, ui)
        ui = nil
    end
    for _, h in ipairs(blocks) do
        pcall(sim.removeObject, h)
    end
    blocks = {}
    print('[Scene] Cleanup complete.')
end
