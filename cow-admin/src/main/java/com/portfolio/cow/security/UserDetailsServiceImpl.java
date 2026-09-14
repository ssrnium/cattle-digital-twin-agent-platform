package com.portfolio.cow.security;

import com.baomidou.mybatisplus.core.conditions.query.LambdaQueryWrapper;
import com.portfolio.cow.common.BizException;
import com.portfolio.cow.common.ResultCode;
import com.portfolio.cow.modules.system.entity.SysRole;
import com.portfolio.cow.modules.system.entity.SysRolePerm;
import com.portfolio.cow.modules.system.entity.SysUser;
import com.portfolio.cow.modules.system.entity.SysUserRole;
import com.portfolio.cow.modules.system.mapper.SysRoleMapper;
import com.portfolio.cow.modules.system.mapper.SysRolePermMapper;
import com.portfolio.cow.modules.system.mapper.SysUserMapper;
import com.portfolio.cow.modules.system.mapper.SysUserRoleMapper;
import lombok.RequiredArgsConstructor;
import org.springframework.security.core.userdetails.UserDetails;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.stereotype.Service;

import java.util.List;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
public class UserDetailsServiceImpl implements UserDetailsService {

    private final SysUserMapper userMapper;
    private final SysUserRoleMapper userRoleMapper;
    private final SysRoleMapper roleMapper;
    private final SysRolePermMapper rolePermMapper;

    @Override
    public UserDetails loadUserByUsername(String username) throws UsernameNotFoundException {
        SysUser user = userMapper.selectOne(
                new LambdaQueryWrapper<SysUser>().eq(SysUser::getUsername, username));
        if (user == null) {
            throw new UsernameNotFoundException("用户不存在: " + username);
        }
        if (!"ENABLED".equals(user.getStatus())) {
            throw new BizException(ResultCode.UNAUTHORIZED.getCode(), "账号已停用");
        }

        List<Long> roleIds = userRoleMapper.selectList(
                        new LambdaQueryWrapper<SysUserRole>().eq(SysUserRole::getUserId, user.getId()))
                .stream().map(SysUserRole::getRoleId).toList();

        List<String> roles = roleIds.isEmpty() ? List.of()
                : roleMapper.selectBatchIds(roleIds).stream().map(SysRole::getRoleCode).toList();

        Set<String> perms = roleIds.isEmpty() ? Set.of()
                : rolePermMapper.selectList(
                        new LambdaQueryWrapper<SysRolePerm>().in(SysRolePerm::getRoleId, roleIds))
                .stream().map(SysRolePerm::getPermCode).collect(Collectors.toSet());

        LoginUser loginUser = new LoginUser();
        loginUser.setId(user.getId());
        loginUser.setUsername(user.getUsername());
        loginUser.setPassword(user.getPassword());
        loginUser.setNickname(user.getNickname());
        loginUser.setRoles(roles);
        loginUser.setPerms(perms);
        return loginUser;
    }
}
