import pytest
import tempfile
from pathlib import Path
import json
import numpy as np
from PIL import Image
import sys

sys.path.append(str(Path(__file__).parent.parent))

from app.analyzers.synthetic_generator.generator import SyntheticCertificateGenerator
from app.analyzers.synthetic_generator.templates import CertificateTemplates
from app.analyzers.synthetic_generator.augmentor import CertificateAugmentor

class TestSyntheticGenerator:
    """Production tests for synthetic data generator"""
    
    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test outputs"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)
    
    @pytest.fixture
    def generator(self, temp_dir):
        """Create generator instance"""
        return SyntheticCertificateGenerator(output_dir=temp_dir)
    
    @pytest.fixture
    def templates(self):
        """Create templates instance"""
        return CertificateTemplates()
    
    @pytest.fixture
    def augmentor(self):
        """Create augmentor instance"""
        return CertificateAugmentor()
    
    def test_generator_initialization(self, generator):
        """Test generator initialization"""
        assert generator is not None
        assert hasattr(generator, 'output_dir')
        assert hasattr(generator, 'templates')
        assert hasattr(generator, 'augmentor')
        
        # Check output directories created
        assert generator.output_dir.exists()
        assert (generator.output_dir / 'images').exists()
        assert (generator.output_dir / 'labels').exists()
    
    def test_template_management(self, templates):
        """Test template management"""
        # List templates
        template_list = templates.list_templates()
        assert isinstance(template_list, list)
        
        # Should have default templates
        assert any('university_en' in t for t in template_list)
        assert any('university_am' in t for t in template_list)
        
        # Get specific template
        template = templates.get_template('university_en')
        assert 'name' in template
        assert 'fields' in template
        assert isinstance(template['fields'], list)
        
        # Validate template structure
        errors = templates.validate_template(template)
        assert len(errors) == 0
    
    def test_synthetic_certificate_generation(self, generator):
        """Test single certificate generation"""
        # Generate English certificate
        cert_data = {
            'name': 'Test User',
            'student_id': 'STU2023-001',
            'university': 'Test University',
            'course': 'Computer Science',
            'gpa': '3.75',
            'issue_date': '2023-06-15'
        }
        
        result = generator.generate_certificate(
            cert_data,
            cert_type='university',
            language='en',
            add_tampering=False
        )
        
        assert 'image_path' in result
        assert 'label_path' in result
        assert 'metadata' in result
        
        # Check files exist
        assert Path(result['image_path']).exists()
        assert Path(result['label_path']).exists()
        
        # Check label content
        with open(result['label_path'], 'r') as f:
            label = json.load(f)
        
        assert label['name'] == cert_data['name']
        assert label['student_id'] == cert_data['student_id']
        assert label['language'] == 'en'
    
    def test_amharic_certificate_generation(self, generator):
        """Test Amharic certificate generation"""
        cert_data = {
            'name': 'ሙሉ ስም',  # Full name in Amharic
            'student_id': 'STU2023-002',
            'university': 'የፈተና ዩኒቨርሲቲ',  # Test University
            'course': 'ኮምፒውተር ሳይንስ',  # Computer Science
            'gpa': '3.50',
            'issue_date': '2023-06-15'
        }
        
        result = generator.generate_certificate(
            cert_data,
            cert_type='university',
            language='am',
            add_tampering=False
        )
        
        assert 'image_path' in result
        assert 'label_path' in result
        
        # Check language in metadata
        with open(result['label_path'], 'r') as f:
            label = json.load(f)
        
        assert label['language'] == 'am'
    
    def test_tampered_certificate_generation(self, generator):
        """Test tampered certificate generation"""
        cert_data = {
            'name': 'Original Name',
            'student_id': 'ORIG123',
            'university': 'Original University',
            'course': 'Original Course',
            'gpa': '3.00',
            'issue_date': '2023-01-01'
        }
        
        result = generator.generate_certificate(
            cert_data,
            cert_type='university',
            language='en',
            add_tampering=True
        )
        
        assert 'image_path' in result
        assert 'label_path' in result
        assert 'metadata' in result
        
        # Check tampering flag in metadata
        metadata = result['metadata']
        assert metadata.get('is_tampered', False) is True
        assert 'tampering_type' in metadata
        
        # Original data should still be in label
        with open(result['label_path'], 'r') as f:
            label = json.load(f)
        
        assert 'original_data' in label
        assert 'tampered_data' in label
    
    def test_augmentation(self, augmentor, temp_dir):
        """Test image augmentation"""
        # Create a simple test image
        test_image = Image.new('RGB', (800, 600), color='white')
        
        # Apply augmentation
        augmented = augmentor.augment_image(test_image, intensity=0.5)
        
        # Should still be an image
        assert isinstance(augmented, Image.Image)
        assert augmented.size == test_image.size
        
        # Test multiple augmentations
        augmented_images = augmentor.augment_for_training(test_image, augmentations_per_image=3)
        assert len(augmented_images) == 4  # Original + 3 augmented
        
        # All should be valid images
        for img in augmented_images:
            assert isinstance(img, Image.Image)
            assert img.size == test_image.size
    
    def test_batch_generation(self, generator, temp_dir):
        """Test batch certificate generation"""
        num_samples = 10
        tampering_ratio = 0.3
        
        results = generator.generate_dataset(
            num_samples=num_samples,
            tampering_ratio=tampering_ratio,
            languages=['en', 'am'],
            certificate_types=['university', 'training']
        )
        
        assert isinstance(results, dict)
        assert 'total_generated' in results
        assert 'languages' in results
        assert 'tampered_count' in results
        
        # Check counts
        assert results['total_generated'] == num_samples
        assert results['tampered_count'] == int(num_samples * tampering_ratio)
        
        # Check files were created
        image_files = list((temp_dir / 'images').glob('*.png'))
        label_files = list((temp_dir / 'labels').glob('*.json'))
        
        assert len(image_files) == num_samples
        assert len(label_files) == num_samples
    
    def test_dataset_metadata(self, generator, temp_dir):
        """Test dataset metadata generation"""
        num_samples = 5
        
        results = generator.generate_dataset(num_samples=num_samples)
        
        # Check metadata file
        metadata_path = temp_dir / 'metadata.json'
        assert metadata_path.exists()
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        assert 'generated_at' in metadata
        assert 'num_samples' in metadata
        assert metadata['num_samples'] == num_samples
        assert 'languages' in metadata
        assert 'certificate_types' in metadata
        assert 'tampering_ratio' in metadata
    
    def test_image_quality(self, generator):
        """Test generated image quality"""
        cert_data = {
            'name': 'Quality Test',
            'student_id': 'QUAL001',
            'university': 'Quality University',
            'course': 'Quality Course',
            'gpa': '3.00',
            'issue_date': '2023-01-01'
        }
        
        result = generator.generate_certificate(cert_data, 'university', 'en')
        
        # Load and verify image
        img = Image.open(result['image_path'])
        
        # Check image properties
        assert img.mode == 'RGB'
        assert img.size[0] > 100  # Reasonable width
        assert img.size[1] > 100  # Reasonable height
        
        # Check it's not empty
        img_array = np.array(img)
        assert np.mean(img_array) < 250  # Not completely white
        assert np.mean(img_array) > 5    # Not completely black
    
    def test_label_structure(self, generator):
        """Test label structure and completeness"""
        cert_data = {
            'name': 'John Doe',
            'student_id': 'TEST123',
            'university': 'Test Uni',
            'course': 'Test Course',
            'gpa': '3.5',
            'issue_date': '2023-06-15'
        }
        
        result = generator.generate_certificate(cert_data, 'university', 'en')
        
        with open(result['label_path'], 'r') as f:
            label = json.load(f)
        
        # Check required fields
        required_fields = ['name', 'student_id', 'university', 'course', 'language']
        for field in required_fields:
            assert field in label
        
        # Check data types
        assert isinstance(label['name'], str)
        assert isinstance(label['student_id'], str)
        assert isinstance(label['language'], str)
        
        # Check metadata
        assert 'generated_at' in label
        assert 'certificate_type' in label
        assert 'template_used' in label
    
    def test_error_handling(self, generator):
        """Test error handling in generator"""
        # Test with invalid language
        with pytest.raises(ValueError):
            generator.generate_certificate({}, 'university', 'invalid_lang')
        
        # Test with invalid certificate type
        with pytest.raises(ValueError):
            generator.generate_certificate({}, 'invalid_type', 'en')
        
        # Test with missing required data (should use defaults)
        result = generator.generate_certificate({}, 'university', 'en')
        assert 'image_path' in result  # Should still generate
    
    def test_parallel_generation(self, temp_dir):
        """Test parallel certificate generation"""
        # This would test the parallel processing capability
        # Note: Might need to adjust based on actual implementation
        
        generator = SyntheticCertificateGenerator(
            output_dir=temp_dir,
            max_workers=2
        )
        
        results = generator.generate_dataset(
            num_samples=20,
            use_parallel=True
        )
        
        assert results['total_generated'] == 20
        assert 'processing_time' in results

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])