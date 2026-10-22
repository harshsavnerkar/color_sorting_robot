-- ============================================================
--  ur5_ik.lua
--  Child script on /UR5
-- ============================================================

local ikEnv, ikGroup, robot, ikTarget, ikTip

function sysCall_init()
    robot    = sim.getObject('.')
    ikTarget = sim.getObject('/IKTarget')
    ikTip    = sim.getObject('/UR5/ikTip')

    for i = 1, 6 do
        local j = sim.getObject('/UR5/joint' .. i)
        sim.setJointMode(j, sim.jointmode_kinematic, 0)
    end

    ikEnv   = simIK.createEnvironment()
    ikGroup = simIK.createGroup(ikEnv)
    simIK.setGroupCalculation(ikEnv, ikGroup, simIK.method_damped_least_squares, 0.05, 50)
    simIK.addElementFromScene(ikEnv, ikGroup, robot, ikTip, ikTarget, simIK.constraint_pose)
end

function sysCall_actuation()
    if ikEnv and ikGroup then
        simIK.handleGroup(ikEnv, ikGroup, {syncWorlds=true, allowError=true})
    end
end

function sysCall_cleanup()
    if ikEnv then
        simIK.eraseEnvironment(ikEnv)
        ikEnv = nil
    end
end
