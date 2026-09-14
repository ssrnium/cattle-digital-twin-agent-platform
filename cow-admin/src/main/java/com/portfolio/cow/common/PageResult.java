package com.portfolio.cow.common;

import com.baomidou.mybatisplus.core.metadata.IPage;
import lombok.Data;

import java.io.Serializable;
import java.util.List;
import java.util.function.Function;

@Data
public class PageResult<T> implements Serializable {

    private List<T> records;
    private Long total;
    private Long page;
    private Long size;

    public static <T> PageResult<T> of(IPage<T> p) {
        PageResult<T> r = new PageResult<>();
        r.setRecords(p.getRecords());
        r.setTotal(p.getTotal());
        r.setPage(p.getCurrent());
        r.setSize(p.getSize());
        return r;
    }

    public static <S, T> PageResult<T> of(IPage<S> p, Function<S, T> mapper) {
        PageResult<T> r = new PageResult<>();
        r.setRecords(p.getRecords().stream().map(mapper).toList());
        r.setTotal(p.getTotal());
        r.setPage(p.getCurrent());
        r.setSize(p.getSize());
        return r;
    }
}
