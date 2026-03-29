# Developer Guide - AI Certificate Analyzer

Comprehensive guide for developers working on the AI Certificate Analyzer project.

## Getting Started

### Development Environment Setup

1. **Fork and clone the repository**
2. **Set up Python virtual environment**
3. **Install dependencies**
4. **Configure environment variables**
5. **Run tests to verify setup**

See [SETUP.md](SETUP.md) for detailed installation instructions.

### Project Structure

```
ai_certificate/
├── app/                    # Main application code
│   ├── analyzers/         # Analysis engines
│   ├── api/               # API endpoints
│   ├── utils/             # Utilities
│   ├── vision/            # Computer vision
│   └── main.py           # Entry point
├── tests/                 # Test suite
├── scripts/               # Utility scripts
├── data/                  # Data storage
├── models/                # ML models
└── docs/                  # Documentation
```

## Development Workflow

### 1. Create Feature Branch

```bash
git checkout -b feature/your-feature-name
```

### 2. Make Changes

Follow coding standards and write tests.

### 3. Run Tests

```bash
pytest tests/ -v
```

### 4. Format Code

```bash
black app/ tests/
flake8 app/ tests/
```

### 5. Commit and Push

```bash
git add .
git commit -m "feat: add your feature"
git push origin feature/your-feature-name
```

### 6. Create Pull Request

Open PR on GitHub with description of changes.

## Coding Standards

### Python Style Guide

- Follow PEP 8
- Use type hints
- Maximum line length: 100 characters
- Use docstrings for all functions/classes


### Code Example

```python
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

class ExampleAnalyzer:
    """
    Example analyzer component.
    
    Args:
        config: Configuration dictionary
        use_cache: Enable caching
    """
    
    def __init__(self, config: Dict[str, Any], use_cache: bool = True):
        self.config = config
        self.use_cache = use_cache
        logger.info("ExampleAnalyzer initialized")
    
    async def analyze(self, data: Any) -> Dict[str, Any]:
        """
        Analyze input data.
        
        Args:
            data: Input data to analyze
            
        Returns:
            Analysis results dictionary
            
        Raises:
            ValueError: If data is invalid
        """
        try:
            # Implementation
            result = self._process_data(data)
            return result
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise
    
    def _process_data(self, data: Any) -> Dict[str, Any]:
        """Private helper method"""
        return {"processed": True}
```

## Adding New Features

### Adding a New Analyzer Component

1. **Create component file** in `app/analyzers/`
2. **Implement base interface**
3. **Add tests** in `tests/`
4. **Update main analyzer** to use new component
5. **Document** in code and README

Example:
```python
# app/analyzers/new_analyzer.py
class NewAnalyzer:
    def __init__(self):
        pass
    
    async def analyze(self, image):
        # Implementation
        return {"result": "data"}
```

### Adding a New API Endpoint

1. **Define Pydantic schemas** in `app/api/schemas.py`
2. **Add route** in `app/api/routes.py`
3. **Add tests** in `tests/test_api.py`
4. **Update API documentation**

Example:
```python
# app/api/routes.py
@router.post("/new-endpoint")
async def new_endpoint(request: NewRequest):
    # Implementation
    return {"status": "success"}
```

### Adding ML Model Support

1. **Create model class** in `app/analyzers/ml_models/`
2. **Implement training script** in `scripts/`
3. **Add model loading** in analyzer
4. **Update configuration** for model path
5. **Add tests** for model inference

## Testing

### Writing Tests

```python
import pytest
from app.analyzers.certificate_analyzer import ProductionCertificateAnalyzer

@pytest.fixture
def analyzer():
    return ProductionCertificateAnalyzer(use_ml=False)

@pytest.mark.asyncio
async def test_analyze_certificate(analyzer):
    # Arrange
    mock_file = create_mock_file()
    
    # Act
    result = await analyzer.analyze_certificate_file(
        mock_file, "test_provider", "test_request"
    )
    
    # Assert
    assert result['authenticity_score'] >= 0
    assert 'analysis_id' in result
```

### Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_analyzer.py -v

# Specific test
pytest tests/test_analyzer.py::test_analyze_certificate -v

# With coverage
pytest tests/ --cov=app --cov-report=html

# Parallel execution
pytest tests/ -n auto
```

## Debugging

### Enable Debug Mode

```bash
# In .env
DEBUG=true
LOG_LEVEL=DEBUG
```

### Using Python Debugger

```python
import pdb; pdb.set_trace()  # Set breakpoint
```

### Logging Best Practices

```python
import logging
logger = logging.getLogger(__name__)

# Use appropriate levels
logger.debug("Detailed diagnostic info")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred", exc_info=True)
logger.critical("Critical failure")
```

### Common Debug Commands

```bash
# Check running processes
ps aux | grep uvicorn

# Monitor logs in real-time
tail -f logs/app.log

# Check Redis keys
redis-cli KEYS "ai_*"

# Monitor system resources
htop  # or top on Windows
```

## Performance Profiling

### Memory Profiling

```python
from memory_profiler import profile

@profile
def memory_intensive_function():
    # Your code here
    pass
```

### Time Profiling

```python
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

# Your code here

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)
```

### Load Testing

```bash
# Install locust
pip install locust

# Run load test
locust -f tests/load_test.py --host=http://localhost:8001
```

## Database Migrations (Future)

When database is implemented:

```bash
# Install Alembic
pip install alembic

# Initialize migrations
alembic init migrations

# Create migration
alembic revision --autogenerate -m "Add analysis_results table"

# Apply migrations
alembic upgrade head

# Rollback
alembic downgrade -1
```

## CI/CD Pipeline

### GitHub Actions Example

```yaml
name: CI/CD

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/ --cov=app
      
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: pip install black flake8
      - run: black --check app/ tests/
      - run: flake8 app/ tests/
```

## Contributing Guidelines

### Code Review Checklist

- [ ] Code follows PEP 8 style guide
- [ ] All functions have docstrings
- [ ] Type hints are used
- [ ] Tests are included
- [ ] Tests pass locally
- [ ] No sensitive data in code
- [ ] Error handling is comprehensive
- [ ] Logging is appropriate
- [ ] Performance impact considered
- [ ] Documentation updated

### Commit Message Format

```
<type>(<scope>): <subject>

<body>

<footer>
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `style`: Formatting
- `refactor`: Code restructuring
- `test`: Adding tests
- `chore`: Maintenance

Example:
```
feat(ocr): add support for Arabic script

- Implement Arabic OCR engine
- Add character validation
- Update multilingual router

Closes #123
```

## Useful Commands

### Development

```bash
# Start development server
python app/main.py

# Run with auto-reload
uvicorn app.main:app --reload --port 8001

# Generate synthetic data
python scripts/generate_synthetic.py --samples 100

# Train models
python scripts/train_donut.py
```

### Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=app --cov-report=html

# Run specific test
pytest tests/test_analyzer.py::test_health_check -v
```

### Code Quality

```bash
# Format code
black app/ tests/ scripts/

# Check linting
flake8 app/ tests/ scripts/

# Type checking
mypy app/

# Security check
bandit -r app/
```

### Docker

```bash
# Build image
docker build -t certanalyzer:dev .

# Run container
docker run -p 8001:8001 certanalyzer:dev

# Docker compose
docker-compose up -d
docker-compose logs -f api
docker-compose down
```

## Troubleshooting Development Issues

### Import Errors

```bash
# Ensure PYTHONPATH is set
export PYTHONPATH="${PYTHONPATH}:$(pwd)"

# Or add to .env
PYTHONPATH=/path/to/project
```

### Model Loading Issues

```bash
# Check model files
ls -la app/models/donut_certificate/

# Test model loading
python -c "from app.analyzers.ml_models.donut_model import DonutCertificateParser; p = DonutCertificateParser()"
```

### Redis Connection Issues

```bash
# Check Redis is running
redis-cli ping

# Check connection
python -c "import redis; r = redis.Redis(); print(r.ping())"
```

## Resources

### Documentation
- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Tesseract OCR](https://github.com/tesseract-ocr/tesseract)
- [PyTorch](https://pytorch.org/docs/)
- [Transformers](https://huggingface.co/docs/transformers/)

### Tools
- [Postman](https://www.postman.com/) - API testing
- [Redis Commander](https://github.com/joeferner/redis-commander) - Redis GUI
- [Grafana](https://grafana.com/) - Monitoring

---

**Developer Guide Version**: 1.0  
**Last Updated**: March 2024
