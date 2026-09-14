package com.portfolio.cow.config;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.modules.cow.entity.CowProfile;
import com.portfolio.cow.modules.cow.mapper.CowProfileMapper;
import com.portfolio.cow.modules.device.entity.Device;
import com.portfolio.cow.modules.device.mapper.DeviceMapper;
import com.portfolio.cow.modules.system.entity.SysRole;
import com.portfolio.cow.modules.system.entity.SysRolePerm;
import com.portfolio.cow.modules.system.entity.SysUser;
import com.portfolio.cow.modules.system.entity.SysUserRole;
import com.portfolio.cow.modules.system.mapper.SysRoleMapper;
import com.portfolio.cow.modules.system.mapper.SysRolePermMapper;
import com.portfolio.cow.modules.system.mapper.SysUserMapper;
import com.portfolio.cow.modules.system.mapper.SysUserRoleMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.boot.CommandLineRunner;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Component;

import java.time.LocalDateTime;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * 空库初始化：账号（启动时 BCrypt 现场编码）、角色权限、103 头牛档案、4 摄像头 + 1 边缘节点。
 * edge-node-01 的固定 deviceKey 见 README（演示用，生产必须更换）。
 */
@Slf4j
@Component
@RequiredArgsConstructor
public class DataInitializer implements CommandLineRunner {

    public static final String EDGE_NODE_ID = "edge-node-01";
    public static final String EDGE_NODE_KEY = "edge-node-01-secret-2026";

    private static final String BARN = "20号牛棚";
    private static final String[] ZONES = {"ZONE-A", "ZONE-B", "ZONE-C", "ZONE-D"};

    private final SysUserMapper userMapper;
    private final SysRoleMapper roleMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final SysRolePermMapper rolePermMapper;
    private final CowProfileMapper cowProfileMapper;
    private final DeviceMapper deviceMapper;
    private final PasswordEncoder passwordEncoder;

    @Override
    public void run(String... args) {
        if (userMapper.selectCount(null) == 0) {
            initUsersAndRoles();
        }
        if (cowProfileMapper.selectCount(null) == 0) {
            initCows();
        }
        if (deviceMapper.selectCount(null) == 0) {
            initDevices();
        }
    }

    private void initUsersAndRoles() {
        Long adminRole = createRole("ADMIN", "系统管理员",
                List.of("*"));
        Long vetRole = createRole("VET", "兽医", List.of(
                "barn:view", "cow:list", "cow:detail", "event:list", "task:list", "task:handle",
                "device:list", "agent:chat"));
        Long breederRole = createRole("BREEDER", "繁育员", List.of(
                "barn:view", "cow:list", "cow:detail", "event:list", "task:list", "task:handle",
                "device:list", "agent:chat"));
        // 牧场智能体（cow-agent）回调业务接口用的 service 账号：
        // 只有业务查询 + 手工建单权限，无系统管理 / 工单流转权限
        Long serviceRole = createRole("SERVICE", "服务账号", List.of(
                "cow:list", "cow:detail", "event:list", "task:list", "task:create", "device:list"));

        Long admin = createUser("admin", "Admin@123", "系统管理员");
        Long vet = createUser("vet", "Vet@123", "兽医-王");
        Long breeder = createUser("breeder", "Breeder@123", "繁育员-李");
        Long svcAgent = createUser("svc-agent", "SvcAgent@123", "牧场智能体服务账号");
        bind(admin, adminRole);
        bind(vet, vetRole);
        bind(breeder, breederRole);
        bind(svcAgent, serviceRole);
        log.info("initialized users: admin / vet / breeder / svc-agent");
    }

    private Long createRole(String code, String name, List<String> perms) {
        SysRole role = new SysRole();
        role.setRoleCode(code);
        role.setRoleName(name);
        role.setCreateTime(LocalDateTime.now());
        roleMapper.insert(role);
        for (String p : perms) {
            SysRolePerm rp = new SysRolePerm();
            rp.setRoleId(role.getId());
            rp.setPermCode(p);
            rolePermMapper.insert(rp);
        }
        return role.getId();
    }

    private Long createUser(String username, String rawPassword, String nickname) {
        SysUser user = new SysUser();
        user.setUsername(username);
        user.setPassword(passwordEncoder.encode(rawPassword)); // 启动时现场编码，不落明文
        user.setNickname(nickname);
        user.setStatus("ENABLED");
        user.setCreateTime(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());
        userMapper.insert(user);
        return user.getId();
    }

    private void bind(Long userId, Long roleId) {
        SysUserRole ur = new SysUserRole();
        ur.setUserId(userId);
        ur.setRoleId(roleId);
        userRoleMapper.insert(ur);
    }

    private void initCows() {
        for (int i = 1; i <= 103; i++) {
            CowProfile cow = new CowProfile();
            cow.setCowId(String.format("COW-%04d", i));
            cow.setEarTag(String.format("ET-%04d", i));
            cow.setBarnId(BARN);
            cow.setZone(ZONES[(i - 1) * ZONES.length / 103]); // 4 个 zone 均分
            cow.setStatus("ACTIVE");
            cow.setCreateTime(LocalDateTime.now());
            cowProfileMapper.insert(cow);
        }
        log.info("initialized 103 cow profiles in {}", BARN);
    }

    private void initDevices() {
        for (int i = 1; i <= 4; i++) {
            Device cam = new Device();
            cam.setDeviceId(String.format("camera-%02d", i));
            cam.setDeviceKey("camera-key-" + i + "-demo");
            cam.setType(Device.TYPE_CAMERA);
            cam.setName("20号牛棚摄像头-" + i);
            cam.setBarnId(BARN);
            cam.setPendingCount(0);
            Map<String, Object> meta = new HashMap<>();
            meta.put("zone", ZONES[i - 1]);
            meta.put("rtsp", "rtsp://192.168.20." + (10 + i) + "/stream1");
            cam.setMeta(meta);
            deviceMapper.insert(cam);
        }
        Device edge = new Device();
        edge.setDeviceId(EDGE_NODE_ID);
        edge.setDeviceKey(EDGE_NODE_KEY);
        edge.setType(Device.TYPE_EDGE_NODE);
        edge.setName("20号牛棚边缘节点");
        edge.setBarnId(BARN);
        edge.setPendingCount(0);
        Map<String, Object> meta = new HashMap<>();
        meta.put("model", "jetson-orin-nano");
        meta.put("note", "断网缓存与恢复演示节点");
        edge.setMeta(meta);
        deviceMapper.insert(edge);
        log.info("initialized 4 cameras + edge node {}", EDGE_NODE_ID);
    }

    /** 供其他组件按 device_id 查询（备用） */
    public boolean deviceExists(String deviceId) {
        return deviceMapper.selectCount(new LambdaQueryWrapper<Device>()
                .eq(Device::getDeviceId, deviceId)) > 0;
    }
}
