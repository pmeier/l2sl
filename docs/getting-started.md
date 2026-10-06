## How do I get started?

In the most minimal setup, you only need to do add one thing to your logging setup, preferably after the
`structlog.configure()` call:

```python
import l2sl

l2sl.configure_stdlib_log_forwarding()
```
