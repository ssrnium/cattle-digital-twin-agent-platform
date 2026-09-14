package com.portfolio.cow.modules.system.controller;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.baomidou.mybatisplus.extension.plugins.pagination.Page;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.PageResult;
import com.portfolio.cow.common.Result;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.system.annotation.OperLog;
import com.portfolio.cow.modules.system.entity.SysRole;
import com.portfolio.cow.modules.system.entity.SysRolePerm;
import com.portfolio.cow.modules.system.mapper.SysRoleMapper;
import com.portfolio.cow.modules.system.mapper.SysRolePermMapper;
import lombok.RequiredArgsConstructor;
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
@RequestMapping("/api/v1/system/roles")
@RequiredArgsConstructor
public class SysRoleController {

    private final SysRoleMapper roleMapper;
    private final SysRolePermMapper rolePermMapper;

    @GetMapping
    public Result<PageResult<SysRole>> page(@RequestParam(defaultValue = "1") long page,
                                            @RequestParam(defaultValue = "10") long size,
                                            @RequestParam(required = false) String keyword) {
        LambdaQueryWrapper<SysRole> wrapper = new LambdaQueryWrapper<SysRole>()
                .like(StringUtils.hasText(keyword), SysRole::getRoleName, keyword)
                .orderByAsc(SysRole::getId);
        return Result.ok(PageResult.of(roleMapper.selectPage(new Page<>(page, size), wrapper)));
    }

    @GetMapping("/all")
    public Result<List<SysRole>> all() {
        return Result.ok(roleMapper.selectList(new LambdaQueryWrapper<SysRole>().orderByAsc(SysRole::getId)));
    }

    @GetMapping("/{id}/perms")
    public Result<List<String>> perms(@PathVariable Long id) {
        List<String> perms = rolePermMapper.selectList(
                        new LambdaQueryWrapper<SysRolePerm>().eq(SysRolePerm::getRoleId, id))
                .stream().map(SysRolePerm::getPermCode).toList();
        return Result.ok(perms);
    }

    @PostMapping
    @OperLog(title = "新增角色")
    @Transactional
    public Result<SysRole> create(@RequestBody Map<String, Object> body) {
        String roleCode = (String) body.get("roleCode");
        if (!StringUtils.hasText(roleCode)) {
            throw new BizException(ResultCode.BAD_REQUEST.getCode(), "roleCode 不能为空");
        }
        Long exists = roleMapper.selectCount(
                new LambdaQueryWrapper<SysRole>().eq(SysRole::getRoleCode, roleCode));
        if (exists > 0) {
            throw new BizException(ResultCode.CONFLICT.getCode(), "角色编码已存在");
        }
        SysRole role = new SysRole();
        role.setRoleCode(roleCode);
        role.setRoleName((String) body.get("roleName"));
        role.setDescription((String) body.get("description"));
        role.setCreateTime(LocalDateTime.now());
        roleMapper.insert(role);
        savePerms(role.getId(), body.get("perms"));
        return Result.ok(role);
    }

    @PutMapping("/{id}")
    @OperLog(title = "修改角色")
    @Transactional
    public Result<SysRole> update(@PathVariable Long id, @RequestBody Map<String, Object> body) {
        SysRole role = roleMapper.selectById(id);
        if (role == null) {
            throw new BizException(ResultCode.NOT_FOUND);
        }
        role.setRoleName((String) body.getOrDefault("roleName", role.getRoleName()));
        role.setDescription((String) body.getOrDefault("description", role.getDescription()));
        roleMapper.updateById(role);
        if (body.containsKey("perms")) {
            rolePermMapper.delete(new LambdaQueryWrapper<SysRolePerm>().eq(SysRolePerm::getRoleId, id));
            savePerms(id, body.get("perms"));
        }
        return Result.ok(role);
    }

    @DeleteMapping("/{id}")
    @OperLog(title = "删除角色")
    @Transactional
    public Result<Void> delete(@PathVariable Long id) {
        roleMapper.deleteById(id);
        rolePermMapper.delete(new LambdaQueryWrapper<SysRolePerm>().eq(SysRolePerm::getRoleId, id));
        return Result.ok();
    }

    private void savePerms(Long roleId, Object perms) {
        if (!(perms instanceof List<?> list)) {
            return;
        }
        for (Object p : list) {
            SysRolePerm rp = new SysRolePerm();
            rp.setRoleId(roleId);
            rp.setPermCode(String.valueOf(p));
            rolePermMapper.insert(rp);
        }
    }
}
