// frontend/pages/profile/index.js
import React, { useState, useContext, useEffect, useRef, useCallback } from 'react';
import { useRouter } from 'next/router';
import { SessionContext } from '../../contexts/SessionContext';
import LoadingSpinner from '../../components/ui/LoadingSpinner';
import InputField from '../../components/ui/InputField';
import LiquidGlassButton from '../../components/ui/LiquidGlassButton';
import SingleSelectPillBoxField from '../../components/ui/SingleSelectPillBoxField';
import MultiSelectPillBoxField from '../../components/ui/MultiSelectPillBoxField';
import LiquidGlassModal from '../../components/ui/LiquidGlassModal';
import { FaPlusCircle, FaCamera } from 'react-icons/fa';

import treatmentsData from '../../../ai_service/src/data/treatments.json';
import accommodationsData from '../../../ai_service/src/data/accommodations.json';

const ProfilePage = () => {
  const {
    userId,
    userEmail,
    authReady,
    fetchUserProfile,
    uploadProfilePhoto,
    saveUserProfile,
    deleteUserProfile,
    deleteAccount,
    isLoading,
    isSaving
  } = useContext(SessionContext);

  const router = useRouter();
  const fileInputRef = useRef(null);

  // State
  const [profileData, setProfileData] = useState({
    profilePhotoUrl: '',
    isPersonalizationEnabled: true,
    nationality: '',
    medicalPurpose: '',
    estimatedBudget: '',
    departureCity: '',
    accommodationPreferences: [],
    medicalHistory: '',
  });
  const [originalProfileData, setOriginalProfileData] = useState({});
  const [formErrors, setFormErrors] = useState({});
  const [loading, setLoading] = useState(true);
  const [modalOpen, setModalOpen] = useState(false);
  const [modalAction, setModalAction] = useState(null);
  const [message, setMessage] = useState('');
  const [initialLoad, setInitialLoad] = useState(true);

  // Options
  const specialties = Array.from(
    new Set(treatmentsData.flatMap(t => t.associated_specialties))
  ).map(s => ({ value: s, label: s }));
  const treatments = treatmentsData.map(t => ({ value: t.id, label: t.name }));
  const medicalPurposeOptions = [
    { label: "By Specialties", options: specialties },
    { label: "By Treatments", options: treatments }
  ];
  const accommodationOptions = Array.from(new Set(
    accommodationsData.flatMap(c => c.accommodations.flatMap(a => a.accessibility_features))
  )).map(f => ({ value: f, label: f }));

  // Redirect if not authenticated
  useEffect(() => {
    if (authReady && !userId) router.push('/login');
  }, [authReady, userId, router]);

  // Load profile on mount
  useEffect(() => {
      const loadProfile = async () => {
          if (authReady && userId) {
              setLoading(true);
              try {
                  const profile = await fetchUserProfile(userId);

                  const safeData = profile ? {
                      ...profile,
                      profilePhotoUrl: profile.profilePhotoUrl || '',
                      isPersonalizationEnabled: profile.isPersonalizationEnabled ?? true,
                      nationality: profile.nationality || '',
                      medicalPurpose: profile.medicalPurpose || '',
                      estimatedBudget: profile.estimatedBudget || '',
                      departureCity: profile.departureCity || '',
                      accommodationPreferences: profile.accommodationPreferences || [],
                      medicalHistory: profile.medicalHistory || '',
                  } : {
                      profilePhotoUrl: '',
                      isPersonalizationEnabled: true,
                      nationality: '',
                      medicalPurpose: '',
                      estimatedBudget: '',
                      departureCity: '',
                      accommodationPreferences: [],
                      medicalHistory: '',
                  };

                  setProfileData(safeData);
                  setOriginalProfileData(safeData);
              } catch (err) {
                  setMessage('Error fetching profile: ' + err.message);
              } finally {
                  setLoading(false);
                  setInitialLoad(false);
              }
          }
      };
      loadProfile();
  }, [authReady, userId, fetchUserProfile]);

  if (initialLoad) return <LoadingSpinner messageType="profile-load" />;

  // Check if data has changed
  const isDirty = JSON.stringify(profileData) !== JSON.stringify(originalProfileData);

  // Handlers
  const handleChange = (e) => {
    const { name, value } = e.target;
    setProfileData(prev => ({ ...prev, [name]: value }));
    setFormErrors(prev => ({ ...prev, [name]: '' }));
  };

  const handleSingleSelectChange = (name, value) => {
    setProfileData(prev => ({ ...prev, [name]: prev[name] === value ? '' : value }));
    setFormErrors(prev => ({ ...prev, [name]: '' }));
  };

  const handleMultiSelectChange = (name, values) => {
    setProfileData(prev => ({ ...prev, [name]: values }));
    setFormErrors(prev => ({ ...prev, [name]: '' }));
  };

  const handleImageUpload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const validTypes = ['image/jpeg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type)) return setMessage('Invalid file type.');
    if (file.size > 5 * 1024 * 1024) return setMessage('File too large.');

    setLoading(true);
    try {
      const url = await uploadProfilePhoto(userId, file);
      if (url) setProfileData(prev => ({ ...prev, profilePhotoUrl: url }));
      setMessage('Profile photo updated.');
    } catch (err) {
      setMessage('Error uploading photo: ' + err.message);
    } finally {
      setLoading(false);
    }
  };

  const validateForm = () => {
    const errors = {};
    if (!profileData.nationality) errors.nationality = 'Please select a nationality.';
    if (!profileData.medicalPurpose) errors.medicalPurpose = 'Please select a medical purpose.';
    if (!profileData.estimatedBudget || Number(profileData.estimatedBudget) <= 0) {
      errors.estimatedBudget = 'Budget must be positive.';
    } else if (Number(profileData.estimatedBudget) < 500) {
      errors.estimatedBudget = 'Budget must be at least 500 USD.';
    }
    if (!profileData.departureCity) errors.departureCity = 'Please enter departure city.';
    if (profileData.accommodationPreferences.length === 0) errors.accommodationPreferences = 'Select at least one preference.';
    setFormErrors(errors);
    return Object.keys(errors).length === 0;
  };

  const handleSaveProfile = async () => {
    if (!userId) {
      setMessage('Error: User ID is not available. Please try again.');
      console.error("Attempted to save profile with no userId.");
      return; 
    }
    if (!validateForm()) {
      console.log("Form validation failed, not saving.");
      return;
    }
    console.log("Attempting to save profile for userId:", userId);
    console.log("Data to be saved:", profileData);
    try {
      const success = await saveUserProfile(userId, profileData);
      if (success) {
        setOriginalProfileData(profileData);
        setMessage('Profile updated successfully!');
        console.log("Profile saved successfully to Firebase.");
      } else {
        setMessage('Failed to update profile.');
        console.error("saveUserProfile returned false.");
      }
    } catch (err) {
      setMessage('Failed to update profile.');
      console.error("Error calling saveUserProfile:", err);
    } finally {
      setModalOpen(false);
    }
};

  const handleCancelEdit = () => {
    setProfileData(originalProfileData);
    setFormErrors({});
    setMessage('');
  };

  const handleClearProfile = () => {
    setModalAction('profile');
    setModalOpen(true);
  };

  const handleDeleteAccount = () => {
    setModalAction('account');
    setModalOpen(true);
  };

  if (loading) return <LoadingSpinner messageType="profile-load" />;

  return (
    <div className="w-full max-w-4xl p-8">
      <div className="bg-gray-800 bg-opacity-50 backdrop-filter backdrop-blur-lg 
          rounded-2xl p-10 border border-gray-700 shadow-xl transition-all duration-300 
          hover:shadow-2xl hover:border-gray-600 w-full">

        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-3xl sm:text-4xl font-extrabold text-white leading-tight">Your Profile</h2>
          <p className="text-gray-400 mt-2 text-base sm:text-lg">Manage your personal information and preferences.</p>
        </div>

        {/* Form */}
        <form className="space-y-6" onSubmit={(e) => e.preventDefault()}>
          <div className="flex flex-col items-center space-y-4">
            <div className="relative w-28 h-28 sm:w-32 sm:h-32 rounded-full overflow-hidden border-4 border-primary/50 shadow-lg group">
              <img
                src={profileData.profilePhotoUrl || "https://placehold.co/128x128/333333/FFFFFF?text=YOU"}
                alt="Profile"
                className="w-full h-full object-cover transition-transform duration-300 transform group-hover:scale-110"
              />
              <label
                htmlFor="profile-photo-upload"
                className="absolute inset-0 bg-black bg-opacity-40 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity duration-300 cursor-pointer"
              >
                <FaCamera className="text-white text-2xl" />
              </label>
              <input
                id="profile-photo-upload"
                type="file"
                ref={fileInputRef}
                style={{ display: 'none' }}
                onChange={handleImageUpload}
                accept="image/*"
              />
              <div className="absolute bottom-0 right-0 transform translate-x-1/4 translate-y-1/4 text-primary-light text-2xl pointer-events-none">
                <FaPlusCircle />
              </div>
            </div>
            <p className="text-gray-200 text-sm">{userEmail}</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <InputField
              label="Nationality"
              name="nationality"
              value={profileData.nationality}
              onChange={handleChange}
              placeholder="e.g., Malaysia"
            />
            <InputField
              label="Departure City"
              name="departureCity"
              value={profileData.departureCity}
              onChange={handleChange}
              placeholder="e.g., Kuala Lumpur"
            />
            <InputField
              label="Estimated Budget (USD)"
              type="number"
              name="estimatedBudget"
              value={profileData.estimatedBudget || ''}
              onChange={handleChange}
              placeholder="e.g., 5000"
            />
            <InputField
              label="Medical History (Optional)"
              name="medicalHistory"
              value={profileData.medicalHistory || ''}
              onChange={handleChange}
              placeholder="e.g., Diabetes"
            />
          </div>

          <div>
            <label className="block text-gray-200 text-sm font-bold mb-2">Medical Purpose</label>
            <div className="max-h-48 overflow-y-auto pr-2 custom-scrollbar">
              <SingleSelectPillBoxField
                name="medicalPurpose"
                options={medicalPurposeOptions}
                value={profileData.medicalPurpose}
                onChange={(val) => handleSingleSelectChange('medicalPurpose', val)}
              />
            </div>
          </div>

          <div>
            <label className="block text-gray-200 text-sm font-bold mb-2">Accommodation Preferences</label>
            <div className="max-h-48 overflow-y-auto pr-2 custom-scrollbar">
              <MultiSelectPillBoxField
                name="accommodationPreferences"
                options={accommodationOptions}
                values={profileData.accommodationPreferences}
                onChange={(vals) => handleMultiSelectChange('accommodationPreferences', vals)}
              />
            </div>
          </div>

          {/* Buttons: Update + Clear */}
          <div className="flex flex-row space-x-4 pt-4">
            <LiquidGlassButton
              type="button"
              onClick={() => {
                setModalAction('updateProfile');
                setModalOpen(true);
              }}
              className={`flex-1 ${isDirty && userId ? 'bg-primary-light' : 'bg-gray-600 cursor-not-allowed'}`}
              disabled={!isDirty || isSaving || !userId}
            >
              Update Profile
            </LiquidGlassButton>

            <LiquidGlassButton
              type="button"
              onClick={() => {
                setModalAction('profile');
                setModalOpen(true);
              }}
              className="flex-1 bg-red-600 hover:bg-red-700 text-white font-semibold py-3 rounded-xl transition-all"
            >
              Clear Profile
            </LiquidGlassButton>
          </div>

          {/* Delete Account */}
          <LiquidGlassButton
            type="button"
            onClick={() => {
              setModalAction('account');
              setModalOpen(true);
            }}
            className="w-full bg-gray-700 hover:bg-gray-600 text-white font-semibold py-3 rounded-xl transition-all mt-4"
          >
            Delete Account
          </LiquidGlassButton>


        </form>

        {message && (
          <p className={`text-center text-sm font-semibold mt-4 ${message.includes('success') ? 'text-green-400' : 'text-red-400'}`}>
            {message}
          </p>
        )}

        {/* Modals */}
        <LiquidGlassModal
          isOpen={modalOpen && modalAction === 'updateProfile'}
          onClose={() => setModalOpen(false)}
          onConfirm={async () => {
            try {
              await handleSaveProfile();
            } catch (err) {
              console.error('Error saving profile:', err);
              setMessage('Failed to update profile.');
            } finally {
              setModalOpen(false);
            }
          }}
          title="Confirm Update Profile"
          message="Are you sure you want to update your profile with these changes?"
          variant="warning"
        />

        <LiquidGlassModal
          isOpen={modalOpen && modalAction === 'profile'}
          onClose={() => setModalOpen(false)}
          onConfirm={async () => {
            try {
              const success = await deleteUserProfile(userId);
              if (success) {
                setProfileData({
                  profilePhotoUrl: '',
                  isPersonalizationEnabled: true,
                  nationality: '',
                  medicalPurpose: '',
                  estimatedBudget: '',
                  departureCity: '',
                  accommodationPreferences: [],
                  medicalHistory: '',
                });
                setOriginalProfileData({});
                setMessage('Profile cleared.');
              } else {
                setMessage('Failed to clear profile.');
              }
            } catch (err) {
              console.error('Error clearing profile:', err);
              setMessage('Failed to clear profile.');
            } finally {
              setModalOpen(false);
            }
          }}
          title="Confirm Clear Profile"
          message="Are you sure you want to clear your profile? This cannot be undone."
          variant="danger"
        />

        <LiquidGlassModal
          isOpen={modalOpen && modalAction === 'account'}
          onClose={() => setModalOpen(false)}
          onConfirm={async () => {
            try {
              const res = await deleteAccount();
              if (res.success) {
                router.push('/login');
              } else {
                setMessage(res.error || 'Failed to delete account.');
              }
            } catch (err) {
              console.error('Error deleting account:', err);
              setMessage('Failed to delete account.');
            } finally {
              setModalOpen(false);
            }
          }}
          title="Confirm Delete Account"
          message="Are you sure you want to delete your account? All your data will be permanently removed."
          variant="danger"
        />
      </div>
    </div>
  );
};

export default ProfilePage;