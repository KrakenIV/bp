import h5py
import numpy as np
import pandas as pd
import dateutil
import os.path

class bitdata(object):
    data_filepath = ''
    source_filename =''
    clean_filename = ''
    filter_filename = ''
    filename = ''
    filename_extension = 'h5'
    source_extension = 'csv'

    batch_size = 1000
    y_col = 'Close'
    x_window_size = 100
    y_window_size = 1
    filter_cols = None
    normalize = True

    nrows = 0
    ncols = 0

    ntrain = 0
    ntest = 0
    train_rate =0.9


    def __init__(self,
                 data_filepath,
                 source_filename,
                 start_date,
                 end_date,
                 filename_extension='h5',
                 source_extension = 'csv',
                 x_windows_size = 100,
                 y_windows_size = 1,
                 filter_cols = None,
                 normalize = True,
                 y_col = 'Close',
                 refresh = False):
        print("> Инициализация модели данных из " + source_filename + " для данных c " + start_date + " по " + end_date)
        self.data_filepath = data_filepath
        self.source_filename = source_filename
        self.filename_extension = filename_extension
        self.source_extension = source_extension
        self.clean_filename = "clean_" + self.source_filename

        self.x_window_size = x_windows_size
        self.y_window_size = y_windows_size
        self.filter_cols = filter_cols
        self.normalize = normalize
        self.y_col = y_col

        self.filter_filename = self.__get_filter_filename(start_date, end_date)
        filter_file = self.filter_filename + "."+source_extension
        print("> Фильтрованый файл ", filter_file)
        if not os.path.isfile(filter_file) or refresh:
            print("> Не найден. Создаем.")
            self.create_filter_date_datafile(start_date, end_date)

        self.clean_filename = self.__get_clean_filename(self.x_window_size,y_windows_size)
        clean_file = self.clean_filename + "." + self.filename_extension
        print("> Очищенный файл ", clean_file)
        if not os.path.isfile(clean_file) or refresh:
            print("> Не найден. Создаем.")
            self.create_clean_datafile()
        self.filename = self.clean_filename

        with h5py.File(clean_file, 'r') as hf:
            self.nrows = hf['x'].shape[0]
            self.ncols = hf['x'].shape[2]

        self.ntrain = int(self.nrows*self.train_rate)
        self.ntest = self.nrows - self.ntrain




    def __get_filter_filename(self, start_date, end_date):
       return self.data_filepath + self.source_filename+ "|" + start_date+"-"+end_date

    def __get_clean_filename(self, x_window, y_window):
        return self.filter_filename + "_x="+str(x_window) +"_y="+str(y_window)

    def get_generator_clean_data(self):
        """Создание генератора для подтягивания записей из файла"""
        clean_file = self.clean_filename + "." + self.filename_extension
        with h5py.File(clean_file, 'r') as hf:
            i = 0
            while True:
                data_x = hf['x'][i:i + self.batch_size]
                data_y = hf['y'][i:i + self.batch_size]
                i += self.batch_size
                yield (data_x, data_y)

    def get_generator_clean_data_test(self):
        """Создание генератора для подтягивания записей из файла для тестирования начиная с индекса ntrain"""
        clean_file = self.clean_filename + "." + self.filename_extension
        with h5py.File(clean_file, 'r') as hf:
            i = self.ntrain
            while True:
                data_x = hf['x'][i:i + self.batch_size]
                data_y = hf['y'][i:i + self.batch_size]
                i += self.batch_size
                yield (data_x, data_y)

    def create_filter_date_datafile(self,start_date, end_date):
        print('> Создание файлов данных с фильтром по времени...')
        filename_in = self.data_filepath + self.source_filename + "." + self.source_extension
        filename_out = self.__get_filter_filename(start_date, end_date) + "."+ self.source_extension
        print('> Сохраняем в файл ',filename_out)
        data = pd.read_csv(filename_in, index_col=0)
        begin = dateutil.parser.parse(start_date)
        end = dateutil.parser.parse(end_date)
        result_data = data.loc[data.index.isin(range(int(begin.timestamp()), int(end.timestamp())))]
        result_data.to_csv(filename_out)
        print('> Отфильтрованные данные сохранены в `' + filename_out + '`')

    # def create_clean_datafile(self, filename_in, filename_out, y_col='Close', batch_size=1000, x_window_size=100,
    #                           y_window_size=1, filter_cols=None, normalise=True):
    def create_clean_datafile(self):
        """Incrementally save a datafile of clean data ready for loading straight into model"""
        """Подготовка данных для последующего моделирования"""
        print('> Создание очищенных x & y файлов с данными...')
        # filename_out = self.data_filepath + self.clean_filename + "." + self.filename_extension
        # filename_in = self.data_filepath + self.source_filename + "." + self.filename_extension
        filename_in = self.filter_filename + "." + self.source_extension
        filename_out = self.clean_filename + "." + self.filename_extension
        print('> Из ', filename_in)
        print('> Создание очищенные массивы в ',filename_out)


        data_gen = self.clean_data_generator(
            filename_in,
            batch_size=self.batch_size,
            x_window_size=self.x_window_size,
            y_window_size=self.y_window_size,
            y_col=self.y_col,
            filter_cols=self.filter_cols,
            normalise=self.normalize
        )

        i = 0

        # Открываем файл на запись
        with h5py.File(filename_out, 'w') as hf:
            x1, y1 = next(data_gen)
            # Initialise hdf5 x, y datasets with first chunk of data
            # Инициализируем hdf5, x, y данные с первыми кусками данных
            rcount_x = x1.shape[0]
            dset_x = hf.create_dataset('x', shape=x1.shape, maxshape=(None, x1.shape[1], x1.shape[2]), chunks=True)
            dset_x[:] = x1
            rcount_y = y1.shape[0]
            dset_y = hf.create_dataset('y', shape=y1.shape, maxshape=(None,), chunks=True)
            dset_y[:] = y1
            print('> Создаем x & y файлы с данными | Группа:', i, end='\n')
            for x_batch, y_batch in data_gen:
                # Append batches to x, y hdf5 datasets
                # Добавляем данные x,y  к hdf5 множествам данных
                # print('> Creating x & y data files | Batch:', i, end='\r')
                print(i, end='\r')
                dset_x.resize(rcount_x + x_batch.shape[0], axis=0)
                dset_x[rcount_x:] = x_batch
                rcount_x += x_batch.shape[0]
                dset_y.resize(rcount_y + y_batch.shape[0], axis=0)
                dset_y[rcount_y:] = y_batch
                rcount_y += y_batch.shape[0]
                i += 1

        # print('> Clean datasets created in file `' + filename_out + '.h5`')
        print('> Очищенные данные сохранены в `' + filename_out + '`')

    def clean_data_generator(self, filepath, batch_size, x_window_size, y_window_size, y_col, filter_cols, normalise):
        """Очистка и нормализация данных в группах  размера `batch_size`"""
        data = pd.read_csv(filepath, index_col=0)

        if (filter_cols):
            # Удаляем все данные колонок из даты, которые не входят в список filter_cols
            rm_cols = set(data.columns) - set(filter_cols)
            for col in rm_cols:
                del data[col]

        # Получаем индекс столбца с прогнозируемых данных
        y_col = list(data.columns).index(y_col)

        num_rows = len(data)
        x_data = []
        y_data = []
        i = 0
        while ((i + x_window_size + y_window_size) <= num_rows):
            x_window_data = data[i:(i + x_window_size)]
            y_window_data = data[(i + x_window_size):(i + x_window_size + y_window_size)]

            # Удаляются все строчки содержащие хотя бы одно пустое значение
            if (x_window_data.isnull().values.any() or y_window_data.isnull().values.any()):
                i += 1
                continue

            # Нормализуем данные
            if (normalise):
                abs_base, x_window_data = self.__zero_base_standardise(x_window_data)
                _, y_window_data = self.__zero_base_standardise(y_window_data, abs_base=abs_base)

            # Усредненный данные по интересующему столбцу
            y_average = np.average(y_window_data.values[:, y_col])
            x_data.append(x_window_data.values)
            y_data.append(y_average)
            i += 1

            # Не выбрасываем значение до тех пор пока не наберется достаточно данных x и y для следующей пачки
            if (i % batch_size == 0):
                # Конвертируем из списка в массив с 3 измерениям [windows, window_val, val_dimension]
                x_np_arr = np.array(x_data)
                y_np_arr = np.array(y_data)
                x_data = []
                y_data = []
                yield (x_np_arr, y_np_arr)

    def __zero_base_standardise(self, data, abs_base=pd.DataFrame()):
        """Standardise dataframe to be zero based percentage returns from i=0"""
        """Нормализация по первому элементу"""
        if (abs_base.empty): abs_base = data.iloc[0]
        data_standardised = (data / abs_base) - 1
        return (abs_base, data_standardised)

    def __min_max_normalise(self, data, data_min=pd.DataFrame(), data_max=pd.DataFrame()):
        """Нормализация Pandas окнаданных используя поколлонный мин-макс нормализацию"""
        if (data_min.empty): data_min = data.min()
        if (data_max.empty): data_max = data.max()
        data_normalised = (data - data_min) / (data_max - data_min)
        return (data_min, data_max, data_normalised)