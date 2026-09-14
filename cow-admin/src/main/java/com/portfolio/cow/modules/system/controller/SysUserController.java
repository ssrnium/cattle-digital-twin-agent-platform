package com.portfolio.cow.modules.system.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.PageResult;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.system.annotation.OperLog;
import com.portfolio.cow.modules.system.entity.SysUser;
import com.portfolio.cow.modules.system.entity.SysUserRole;
import com.portfolio.cow.modules.system.mapper.SysUserMapper;
import com.portfolio.cow.modules.system.mapper.SysUserRoleMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.time.LocalDateTime;
import java.util.List;
import java.util.Map;

@RestController
@RequestMapping("/api/v1/system/users")
@RequiredArgsConstructor
public class SysUserController {

    private final SysUserMapper userMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final PasswordEncoder passwordEncoder;

    @GetMapping
    public Result<PageResult<SysUser>> page(@RequestParam(defaultValue = "1") long page,
                                            @RequestParam(defaultValue = "10") long size,
                                            @RequestParam(required = false) String keyword) {
        LambdaQueryWrapper<SysUser> wrapper = new LambdaQueryWrapper<SysUser>()
                .like(StringUtils.hasText(keyword), SysUser::getUsername, keyword)
                .orderByAsc(SysUser::getId);
        return Result.ok(PageResult.of(userMapper.selectPage(new Page<>(page, size), wrapper)));
    }

    /** 全量简要列表，供工单分派下拉使用 */
    @GetMapping("/options")
    public Result<List<SysUser>> options() {
        return Result.ok(userMapper.selectList(new LambdaQueryWrapper<SysUser>()
                .eq(SysUser::getStatus, "ENABLED").orderByAsc(SysUser::getId)));
    }

    @PostMapping
    @OperLog(title = "新增用户")
    @Transactional
    public Result<SysUser> create(@RequestBody Map<String, Object> body) {
        String username = (String) body.get("username");
        if (!StringUtils.hasText(username)) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "username 不能为空");
        }
        Long exists = userMapper.selectCount(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, username));
        if (exists > 0) {
            throw new BizException(ResultCode.CONFLICT.getCode(), "用户名已存在");
        }
        SysUser user = new SysUser();
        user.setUsername(username);
        user.setNickname((String) body.get("nickname"));
        user.setPhone((String) body.get("phone"));
        user.setStatus("ENABLED");
        String raw = StringUtils.hasText((String) body.get("password"))
                ? (String) body.get("password") : "Init@123";
        user.setPassword(passwordEncoder.encode(raw));
        user.setCreateTime(LocalDateTime.now());
        user.setUpdateTime(LocalDateTime.now());
        userMapper.insert(user);
        saveRoles(user.getId(), body.get("roleIds"));
        return Result.ok(user);
    }

    @PutMapping("/{id}")
    @OperLog(title = "修改用户")
    @Transactional
    public Result<SysUser> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        SysUser user = userMapper.selectById(id);
        if (user == null) {
            throw new BizException(ResultCode.NOT_FOUND);
        }
        user.setNickname((String) body.getOrDefault("nickname", user.getNickname()));
        user.setPhone((String) body.getOrDefault("phone", user.getPhone()));
        user.setStatus((String) body.getOrDefault("status", user.getStatus()));
        if (StringUtils.hasText((String) body.get("password"))) {
            user.setPassword(passwordEncoder.encode((String) body.get("password")));
        }
        user.setUpdateTime(LocalDateTime.now());
        userMapper.updateById(user);
        if (body.containsKey("roleIds")) {
            userRoleMapper.delete(new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, id));
            saveRoles(id, body.get("roleIds"));
        }
        return Result.ok(user);
    }

    @DeleteMapping("/{id}")
    @OperLog(title = "删除用户")
    @Transactional
    public Result<Void> delete(@PathVariable Long id) {
        userMapper.deleteById(id);
        userRoleMapper.delete(new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, id));
        return Result.ok();
    }

    @SuppressWarnings("unchecked")
    private void saveRoles(Long userId, Object roleIds) {
        if (!(roleIds instanceof List<?> list)) {
            return;
        }
        for (Object rid : list) {
            SysUserRole ur = new SysUserRole();
            ur.setUserId(userId);
            ur.setRoleId(Long.valueOf(String.valueOf(rid)));
            userRoleMapper.insert(ur);
        }
    }
}
