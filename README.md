# zfs_rotational_check

Python script that checks if given pool consists only of SSD

## Usage

```bash
$ ./zfs_rotational_check fast_pool
Pool contains only SSD: True
```

```
$ ./zfs_rotational_check slow_pool
Pool contains only SSD: False
```
