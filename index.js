import React, { useState, useEffect } from 'react';
import { Plus, Filter, TrendingUp, Users, Package, AlertCircle, Download, Upload, Search, X, Edit2, Trash2, Calendar } from 'lucide-react';
import * as XLSX from 'xlsx';

const ProductManagementSystem = () => {
  const [currentPage, setCurrentPage] = useState('dashboard');
  const [products, setProducts] = useState([]);
  const [searchTerm, setSearchTerm] = useState('');
  const [filterColumn, setFilterColumn] = useState('all');
  const [showAddModal, setShowAddModal] = useState(false);
  const [editingProduct, setEditingProduct] = useState(null);

  useEffect(() => {
    const savedProducts = localStorage.getItem('products');
    if (savedProducts) {
      setProducts(JSON.parse(savedProducts));
    }
  }, []);

  useEffect(() => {
    if (products.length > 0) {
      localStorage.setItem('products', JSON.stringify(products));
    }
  }, [products]);

  const calculateRenewalDate = (activationDate, validityMonths) => {
    if (!activationDate || !validityMonths) return '';
    const date = new Date(activationDate);
    date.setMonth(date.getMonth() + parseInt(validityMonths));
    return date.toISOString().split('T')[0];
  };

  const isExpired = (renewalDate) => {
    if (!renewalDate) return false;
    return new Date(renewalDate) < new Date();
  };

  const exportToExcel = () => {
    const ws = XLSX.utils.json_to_sheet(products);
    const wb = XLSX.utils.book_new();
    XLSX.utils.book_append_sheet(wb, ws, 'Products');
    XLSX.writeFile(wb, `Product_Inventory_${new Date().toISOString().split('T')[0]}.xlsx`);
  };

  const importFromExcel = (e) => {
    const file = e.target.files[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (evt) => {
      const bstr = evt.target.result;
      const wb = XLSX.read(bstr, { type: 'binary' });
      const wsname = wb.SheetNames[0];
      const ws = wb.Sheets[wsname];
      const data = XLSX.utils.sheet_to_json(ws);
      setProducts(data);
    };
    reader.readAsBinaryString(file);
  };

  const saveProduct = (productData) => {
    if (editingProduct) {
      setProducts(products.map(p => p.id === editingProduct.id ? { ...productData, id: editingProduct.id } : p));
    } else {
      setProducts([...products, { ...productData, id: Date.now() }]);
    }
    setShowAddModal(false);
    setEditingProduct(null);
  };

  const deleteProduct = (id) => {
    if (window.confirm('Are you sure you want to delete this product?')) {
      setProducts(products.filter(p => p.id !== id));
    }
  };

  const filteredProducts = products.filter(product => {
    if (!searchTerm) return true;
    if (filterColumn === 'all') {
      return Object.values(product).some(val => 
        String(val).toLowerCase().includes(searchTerm.toLowerCase())
      );
    }
    return String(product[filterColumn] || '').toLowerCase().includes(searchTerm.toLowerCase());
  });

  const expiredProducts = products.filter(p => isExpired(p.renewalDate));

  const industryAnalytics = products.reduce((acc, product) => {
    const industry = product.industryCategory || 'Uncategorized';
    acc[industry] = (acc[industry] || 0) + 1;
    return acc;
  }, {});

  const clients = [...new Set(products.map(p => p.endUserName).filter(Boolean))];

  const Dashboard = () => (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Total Products</p>
              <p className="text-3xl font-bold text-gray-800">{products.length}</p>
            </div>
            <Package className="w-12 h-12 text-blue-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Expired Products</p>
              <p className="text-3xl font-bold text-red-600">{expiredProducts.length}</p>
            </div>
            <AlertCircle className="w-12 h-12 text-red-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Total Clients</p>
              <p className="text-3xl font-bold text-gray-800">{clients.length}</p>
            </div>
            <Users className="w-12 h-12 text-green-500" />
          </div>
        </div>
        
        <div className="bg-white rounded-lg shadow p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-gray-500 text-sm">Industries Served</p>
              <p className="text-3xl font-bold text-gray-800">{Object.keys(industryAnalytics).length}</p>
            </div>
            <TrendingUp className="w-12 h-12 text-purple-500" />
          </div>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
          <AlertCircle className="text-red-500" />
          Expired Subscriptions ({expiredProducts.length})
        </h3>
        {expiredProducts.length === 0 ? (
          <p className="text-gray-500">No expired subscriptions</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-4 py-2 text-left">S/N#</th>
                  <th className="px-4 py-2 text-left">Product Name</th>
                  <th className="px-4 py-2 text-left">Client</th>
                  <th className="px-4 py-2 text-left">Renewal Date</th>
                  <th className="px-4 py-2 text-left">Days Overdue</th>
                </tr>
              </thead>
              <tbody>
                {expiredProducts.map(product => {
                  const daysOverdue = Math.floor((new Date() - new Date(product.renewalDate)) / (1000 * 60 * 60 * 24));
                  return (
                    <tr key={product.id} className="border-b hover:bg-gray-50">
                      <td className="px-4 py-2">{product.serialNumber}</td>
                      <td className="px-4 py-2">{product.productName}</td>
                      <td className="px-4 py-2">{product.endUserName}</td>
                      <td className="px-4 py-2 text-red-600">{product.renewalDate}</td>
                      <td className="px-4 py-2 text-red-600 font-semibold">{daysOverdue} days</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );

  const ProductsList = () => (
    <div className="space-y-4">
      <div className="bg-white rounded-lg shadow p-4">
        <div className="flex flex-col md:flex-row gap-4 items-center justify-between">
          <div className="flex gap-2 w-full md:w-auto">
            <select 
              className="px-4 py-2 border rounded-lg"
              value={filterColumn}
              onChange={(e) => setFilterColumn(e.target.value)}
            >
              <option value="all">All Columns</option>
              <option value="serialNumber">S/N#</option>
              <option value="productName">Product Name</option>
              <option value="endUserName">Client Name</option>
              <option value="deviceUID">Device UID</option>
              <option value="industryCategory">Industry</option>
            </select>
            <div className="relative flex-1 md:w-80">
              <Search className="absolute left-3 top-3 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search products..."
                className="w-full pl-10 pr-4 py-2 border rounded-lg"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
            </div>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="flex items-center gap-2 bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700"
          >
            <Plus className="w-4 h-4" />
            Add Product
          </button>
        </div>
      </div>

      <div className="bg-white rounded-lg shadow overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left">S/N#</th>
                <th className="px-4 py-3 text-left">OEM S/N#</th>
                <th className="px-4 py-3 text-left">Product</th>
                <th className="px-4 py-3 text-left">Model</th>
                <th className="px-4 py-3 text-left">Client</th>
                <th className="px-4 py-3 text-left">Industry</th>
                <th className="px-4 py-3 text-left">Renewal Date</th>
                <th className="px-4 py-3 text-left">Status</th>
                <th className="px-4 py-3 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredProducts.map(product => (
                <tr key={product.id} className="border-b hover:bg-gray-50">
                  <td className="px-4 py-3">{product.serialNumber}</td>
                  <td className="px-4 py-3">{product.oemSerialNumber}</td>
                  <td className="px-4 py-3">{product.productName}</td>
                  <td className="px-4 py-3">{product.model}</td>
                  <td className="px-4 py-3">{product.endUserName}</td>
                  <td className="px-4 py-3">{product.industryCategory}</td>
                  <td className="px-4 py-3">{product.renewalDate}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-1 rounded text-xs ${
                      isExpired(product.renewalDate) 
                        ? 'bg-red-100 text-red-700' 
                        : 'bg-green-100 text-green-700'
                    }`}>
                      {isExpired(product.renewalDate) ? 'Expired' : 'Active'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => {
                          setEditingProduct(product);
                          setShowAddModal(true);
                        }}
                        className="text-blue-600 hover:text-blue-800"
                      >
                        <Edit2 className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => deleteProduct(product.id)}
                        className="text-red-600 hover:text-red-800"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );

  const Analytics = () => (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6">
        <h3 className="text-lg font-semibold mb-4">Industry Distribution</h3>
        <div className="space-y-4">
          {Object.entries(industryAnalytics).map(([industry, count]) => (
            <div key={industry}>
              <div className="flex justify-between mb-1">
                <span className="text-sm font-medium">{industry}</span>
                <span className="text-sm text-gray-600">{count} products</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-blue-600 h-2 rounded-full"
                  style={{ width: `${(count / products.length) * 100}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Network Type Distribution</h3>
          <div className="space-y-3">
            {['2G', '4G'].map(type => {
              const count = products.filter(p => p.networkType === type).length;
              return (
                <div key={type} className="flex justify-between items-center">
                  <span>{type}</span>
                  <span className="font-semibold">{count}</span>
                </div>
              );
            })}
          </div>
        </div>

        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">SIM Provider Distribution</h3>
          <div className="space-y-3">
            {['VI', 'AIRTEL'].map(provider => {
              const count = products.filter(p => p.simProvider === provider).length;
              return (
                <div key={provider} className="flex justify-between items-center">
                  <span>{provider}</span>
                  <span className="font-semibold">{count}</span>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );

  const ClientsList = () => {
    const clientDetails = clients.map(client => ({
      name: client,
      products: products.filter(p => p.endUserName === client),
      totalProducts: products.filter(p => p.endUserName === client).length,
      expiredProducts: products.filter(p => p.endUserName === client && isExpired(p.renewalDate)).length,
      industries: [...new Set(products.filter(p => p.endUserName === client).map(p => p.industryCategory))]
    }));

    return (
      <div className="space-y-4">
        <div className="bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold mb-4">Client List ({clients.length})</h3>
          <div className="space-y-4">
            {clientDetails.map((client, idx) => (
              <div key={idx} className="border rounded-lg p-4 hover:bg-gray-50">
                <div className="flex justify-between items-start mb-2">
                  <h4 className="font-semibold text-lg">{client.name}</h4>
                  <div className="flex gap-4 text-sm">
                    <span className="text-blue-600">{client.totalProducts} products</span>
                    {client.expiredProducts > 0 && (
                      <span className="text-red-600">{client.expiredProducts} expired</span>
                    )}
                  </div>
                </div>
                <div className="flex gap-2 flex-wrap">
                  {client.industries.map((industry, i) => (
                    <span key={i} className="px-2 py-1 bg-gray-100 rounded text-xs">
                      {industry}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  };

  const ProductModal = () => {
    const [formData, setFormData] = useState(editingProduct || {
      serialNumber: '',
      oemSerialNumber: '',
      productName: '',
      model: '',
      networkType: '4G',
      cableLength: '',
      installationDate: '',
      activationDate: '',
      validityPeriod: '',
      renewalDate: '',
      deviceUID: '',
      simProvider: 'VI',
      simNumber: '',
      channelPartner: '',
      endUserName: '',
      industryCategory: ''
    });
    const [errors, setErrors] = useState({});

    useEffect(() => {
      if (formData.activationDate && formData.validityPeriod) {
        const renewal = calculateRenewalDate(formData.activationDate, formData.validityPeriod);
        setFormData(prev => ({ ...prev, renewalDate: renewal }));
      }
    }, [formData.activationDate, formData.validityPeriod]);

    const validateForm = () => {
      const newErrors = {};
      
      if (!formData.serialNumber) newErrors.serialNumber = 'S/N# is required';
      if (!formData.productName) newErrors.productName = 'Product Name is required';
      if (!formData.activationDate) newErrors.activationDate = 'Activation Date is required';
      if (!formData.validityPeriod) newErrors.validityPeriod = 'Validity Period is required';
      if (!formData.deviceUID) newErrors.deviceUID = 'Device UID is required';
      if (!formData.endUserName) newErrors.endUserName = 'End User Name is required';
      if (!formData.industryCategory) newErrors.industryCategory = 'Industry Category is required';
      
      setErrors(newErrors);
      return Object.keys(newErrors).length === 0;
    };

    const handleSubmit = () => {
      if (validateForm()) {
        saveProduct(formData);
        setErrors({});
      }
    };

    return (
      <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center p-4 z-50 overflow-y-auto">
        <div className="bg-white rounded-lg max-w-4xl w-full my-8">
          <div className="p-6 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center mb-6">
              <h2 className="text-2xl font-bold">
                {editingProduct ? 'Edit Product' : 'Add New Product'}
              </h2>
              <button
                onClick={() => {
                  setShowAddModal(false);
                  setEditingProduct(null);
                }}
                className="text-gray-500 hover:text-gray-700"
              >
                <X className="w-6 h-6" />
              </button>
            </div>

            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium mb-1">S/N# *</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.serialNumber ? 'border-red-500' : ''}`}
                    value={formData.serialNumber}
                    onChange={(e) => setFormData({...formData, serialNumber: e.target.value})}
                  />
                  {errors.serialNumber && <p className="text-red-500 text-xs mt-1">{errors.serialNumber}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">OEM S/N#</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.oemSerialNumber}
                    onChange={(e) => setFormData({...formData, oemSerialNumber: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Product Name *</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.productName ? 'border-red-500' : ''}`}
                    value={formData.productName}
                    onChange={(e) => setFormData({...formData, productName: e.target.value})}
                  />
                  {errors.productName && <p className="text-red-500 text-xs mt-1">{errors.productName}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Model</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.model}
                    onChange={(e) => setFormData({...formData, model: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Network Type</label>
                  <select
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.networkType}
                    onChange={(e) => setFormData({...formData, networkType: e.target.value})}
                  >
                    <option value="2G">2G</option>
                    <option value="4G">4G</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Cable Length (for DWLR)</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.cableLength}
                    onChange={(e) => setFormData({...formData, cableLength: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Installation Date</label>
                  <input
                    type="date"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.installationDate}
                    onChange={(e) => setFormData({...formData, installationDate: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Activation Date *</label>
                  <input
                    type="date"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.activationDate ? 'border-red-500' : ''}`}
                    value={formData.activationDate}
                    onChange={(e) => setFormData({...formData, activationDate: e.target.value})}
                  />
                  {errors.activationDate && <p className="text-red-500 text-xs mt-1">{errors.activationDate}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Validity Period (months) *</label>
                  <input
                    type="number"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.validityPeriod ? 'border-red-500' : ''}`}
                    value={formData.validityPeriod}
                    onChange={(e) => setFormData({...formData, validityPeriod: e.target.value})}
                  />
                  {errors.validityPeriod && <p className="text-red-500 text-xs mt-1">{errors.validityPeriod}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Renewal Date (Auto-calculated)</label>
                  <input
                    type="date"
                    disabled
                    className="w-full px-3 py-2 border rounded-lg bg-gray-100"
                    value={formData.renewalDate}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Device UID *</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.deviceUID ? 'border-red-500' : ''}`}
                    value={formData.deviceUID}
                    onChange={(e) => setFormData({...formData, deviceUID: e.target.value})}
                  />
                  {errors.deviceUID && <p className="text-red-500 text-xs mt-1">{errors.deviceUID}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">SIM Provider</label>
                  <select
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.simProvider}
                    onChange={(e) => setFormData({...formData, simProvider: e.target.value})}
                  >
                    <option value="VI">VI</option>
                    <option value="AIRTEL">AIRTEL</option>
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">SIM Number</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.simNumber}
                    onChange={(e) => setFormData({...formData, simNumber: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Channel Partner</label>
                  <input
                    type="text"
                    className="w-full px-3 py-2 border rounded-lg"
                    value={formData.channelPartner}
                    onChange={(e) => setFormData({...formData, channelPartner: e.target.value})}
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">End User Name *</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.endUserName ? 'border-red-500' : ''}`}
                    value={formData.endUserName}
                    onChange={(e) => setFormData({...formData, endUserName: e.target.value})}
                  />
                  {errors.endUserName && <p className="text-red-500 text-xs mt-1">{errors.endUserName}</p>}
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">Industry Category *</label>
                  <input
                    type="text"
                    className={`w-full px-3 py-2 border rounded-lg ${errors.industryCategory ? 'border-red-500' : ''}`}
                    value={formData.industryCategory}
                    onChange={(e) => setFormData({...formData, industryCategory: e.target.value})}
                  />
                  {errors.industryCategory && <p className="text-red-500 text-xs mt-1">{errors.industryCategory}</p>}
                </div>
              </div>

              {Object.keys(errors).length > 0 && (
                <div className="bg-red-50 border border-red-200 rounded-lg p-4">
                  <p className="text-red-800 font-semibold mb-2">Please fix the following errors:</p>
                  <ul className="list-disc list-inside text-red-600 text-sm space-y-1">
                    {Object.values(errors).map((error, idx) => (
                      <li key={idx}>{error}</li>
                    ))}
                  </ul>
                </div>
              )}

              <div className="flex justify-end gap-4">
                <button
                  onClick={() => {
                    setShowAddModal(false);
                    setEditingProduct(null);
                  }}
                  className="px-6 py-2 border rounded-lg hover:bg-gray-50"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSubmit}
                  className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
                >
                  {editingProduct ? 'Update' : 'Add'} Product
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    );
  };

  return (
    <div className="min-h-screen bg-gray-100">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-4">
          <div className="flex justify-between items-center">
            <h1 className="text-2xl font-bold text-gray-800">Product Management System</h1>
            <div className="flex gap-2">
              <label className="flex items-center gap-2 px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 cursor-pointer">
                <Upload className="w-4 h-4" />
                Import Excel
                <input type="file" accept=".xlsx,.xls" onChange={importFromExcel} className="hidden" />
              </label>
              <button
                onClick={exportToExcel}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              >
                <Download className="w-4 h-4" />
                Export Excel
              </button>
            </div>
          </div>
        </div>
      </header>

      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex gap-6">
            {[
              { id: 'dashboard', label: 'Dashboard', icon: TrendingUp },
              { id: 'products', label: 'All Products', icon: Package },
              { id: 'analytics', label: 'Analytics', icon: TrendingUp },
              { id: 'clients', label: 'Clients', icon: Users }
            ].map(item => (
              <button
                key={item.id}
                onClick={() => setCurrentPage(item.id)}
                className={`flex items-center gap-2 px-4 py-4 border-b-2 transition-colors ${
                  currentPage === item.id
                    ? 'border-blue-600 text-blue-600'
                    : 'border-transparent text-gray-600 hover:text-gray-800'
                }`}
              >
                <item.icon className="w-4 h-4" />
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-8">
        {currentPage === 'dashboard' && <Dashboard />}
        {currentPage === 'products' && <ProductsList />}
        {currentPage === 'analytics' && <Analytics />}
        {currentPage === 'clients' && <ClientsList />}
      </main>

      {showAddModal && <ProductModal />}
    </div>
  );
};

export default ProductManagementSystem;